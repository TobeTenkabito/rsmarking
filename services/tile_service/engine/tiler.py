from collections import OrderedDict
import logging
import os
from threading import RLock, local
import time

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling

from services.tile_service.core.config import settings

from .stats import StatsManager
from .utils import get_tile_window

logger = logging.getLogger("tile_service.engine")


try:
    from scipy import ndimage as scipy_ndimage
except ImportError:
    scipy_ndimage = None

try:
    from .rendering import render_tile

    HAS_FAST_TILER = True
except (ImportError, ValueError):
    render_tile = None
    HAS_FAST_TILER = False

try:
    from .translator import fast_stretch_and_stack
except (ImportError, ValueError):
    fast_stretch_and_stack = None


_ENGINE_CACHE_MAXSIZE = max(1, int(os.getenv("TILE_ENGINE_CACHE_SIZE", "16")))
_ENGINE_CACHE = OrderedDict()
_ENGINE_CACHE_LOCK = RLock()
_RASTER_DIAGNOSTICS_LOGGED = set()
_RASTER_DIAGNOSTICS_LOCK = RLock()


def get_tile_engine(file_path: str):
    normalized_path = os.path.abspath(file_path)

    with _ENGINE_CACHE_LOCK:
        engine = _ENGINE_CACHE.get(normalized_path)
        if engine is None:
            engine = TileEngine(normalized_path)
            _ENGINE_CACHE[normalized_path] = engine
        else:
            _ENGINE_CACHE.move_to_end(normalized_path)

        while len(_ENGINE_CACHE) > _ENGINE_CACHE_MAXSIZE:
            _, evicted = _ENGINE_CACHE.popitem(last=False)
            evicted.close()

        return engine


def clear_tile_engine_cache():
    with _ENGINE_CACHE_LOCK:
        for engine in _ENGINE_CACHE.values():
            engine.close()
        _ENGINE_CACHE.clear()


def _file_mtime_ns(file_path: str):
    try:
        return os.stat(file_path).st_mtime_ns
    except OSError:
        return 0


def _profile_enabled() -> bool:
    return bool(getattr(settings, "TILE_PROFILE", False)) or os.getenv("TILE_PROFILE") == "1"


def _alpha_mode() -> str:
    mode = str(getattr(settings, "TILE_ALPHA_MODE", "auto") or "auto").strip().lower()
    if mode not in {"auto", "data"}:
        return "auto"
    return mode


def _raster_open_mode() -> str:
    mode = str(getattr(settings, "TILE_RASTER_OPEN_MODE", "per_request") or "per_request").strip().lower()
    if mode not in {"per_request", "thread_local"}:
        return "per_request"
    return mode


def _resampling_mode() -> str:
    mode = str(getattr(settings, "TILE_RESAMPLING_MODE", "quality") or "quality").strip().lower()
    if mode not in {"quality", "fast", "nearest", "bilinear"}:
        return "quality"
    return mode


def _safe_basename(file_path: str) -> str:
    return os.path.basename(file_path)


class TileEngine:
    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self._src = None
        self._stats_manager = StatsManager()
        self._transformer = None
        self._transformer_key = None
        self._file_mtime_ns = None
        self._crs_wgs84 = "EPSG:4326"
        self._lock = RLock()
        self._thread_local = local()

    def _get_src(self, current_mtime_ns: int | None = None):
        src, _ = self._open_src(current_mtime_ns)
        return src

    def _open_src(self, current_mtime_ns: int | None = None):
        if current_mtime_ns is None:
            current_mtime_ns = _file_mtime_ns(self.file_path)

        if _raster_open_mode() == "thread_local":
            state = getattr(self._thread_local, "src_state", None)
            if state is not None:
                src = state.get("src")
                if (
                    state.get("file_path") == self.file_path
                    and state.get("mtime_ns") == current_mtime_ns
                    and src is not None
                    and not getattr(src, "closed", False)
                ):
                    self._refresh_file_state(current_mtime_ns)
                    return src, False

                if src is not None and not getattr(src, "closed", False):
                    src.close()

            src = rasterio.open(self.file_path)
            self._thread_local.src_state = {
                "file_path": self.file_path,
                "mtime_ns": current_mtime_ns,
                "src": src,
            }
            self._refresh_file_state(current_mtime_ns)
            self._log_raster_diagnostics(src)
            return src, False

        src = rasterio.open(self.file_path)
        self._refresh_file_state(current_mtime_ns)
        self._log_raster_diagnostics(src)
        return src, True

    def _log_raster_diagnostics(self, src):
        if not _profile_enabled():
            return

        with _RASTER_DIAGNOSTICS_LOCK:
            if self.file_path in _RASTER_DIAGNOSTICS_LOGGED:
                return
            _RASTER_DIAGNOSTICS_LOGGED.add(self.file_path)

        try:
            try:
                overviews = src.overviews(1) if getattr(src, "count", 0) >= 1 else []
            except Exception:
                overviews = []

            logger.info(
                "tile_raster_profile path=%s driver=%s width=%s height=%s count=%s "
                "crs=%s is_tiled=%s block_shapes=%s overviews_1=%s",
                _safe_basename(self.file_path),
                getattr(src, "driver", None),
                getattr(src, "width", None),
                getattr(src, "height", None),
                getattr(src, "count", None),
                getattr(src, "crs", None),
                getattr(src, "is_tiled", None),
                getattr(src, "block_shapes", None),
                overviews,
            )
        except Exception:
            logger.warning("Failed to log raster diagnostics for %s", _safe_basename(self.file_path))

    def _refresh_file_state(self, current_mtime_ns: int):
        with self._lock:
            file_changed = (
                self._file_mtime_ns is not None
                and current_mtime_ns != self._file_mtime_ns
            )
            if file_changed:
                StatsManager.invalidate_file(self.file_path)
                self._stats_manager.clear()
                self._transformer = None
                self._transformer_key = None
            elif self._file_mtime_ns is None:
                self._stats_manager.clear()

            self._file_mtime_ns = current_mtime_ns

    def _get_transformer(self, src, current_mtime_ns: int):
        transformer_key = (self.file_path, current_mtime_ns, str(src.crs))
        with self._lock:
            if self._transformer is None or self._transformer_key != transformer_key:
                self._transformer = Transformer.from_crs(
                    self._crs_wgs84,
                    src.crs,
                    always_xy=True,
                )
                self._transformer_key = transformer_key
            return self._transformer

    def read_tile(self, x: int, y: int, z: int, bands: list = None, stats: dict = None):
        profile = _profile_enabled()
        alpha_mode = _alpha_mode()
        timings = {}
        total_start = time.perf_counter()
        last_mark = total_start

        def mark(stage: str):
            nonlocal last_mark
            if not profile:
                return
            now = time.perf_counter()
            timings[stage] = (now - last_mark) * 1000.0
            last_mark = now

        if not os.path.exists(self.file_path):
            self.close()
            return None

        src = None
        close_src = False
        tile_result = None
        try:
            current_mtime_ns = _file_mtime_ns(self.file_path)
            src, close_src = self._open_src(current_mtime_ns)
            mark("source")

            valid_bands = bands if bands else list(range(1, min(4, src.count) + 1))
            valid_bands = [b for b in valid_bands if 1 <= b <= src.count] or [1]
            transformer = self._get_transformer(src, current_mtime_ns)
            window = get_tile_window(x, y, z, src, transformer)
            mark("window")

            resampling = self._select_resampling(src, valid_bands[0], window)
            data = src.read(
                valid_bands,
                window=window,
                out_shape=(len(valid_bands), settings.TILE_SIZE, settings.TILE_SIZE),
                resampling=resampling,
                boundless=True,
                fill_value=0,
                out_dtype="float32",
            )

            if data.dtype != np.float32 or not data.flags.c_contiguous:
                data = np.ascontiguousarray(data, dtype=np.float32)
            mark("read")

            alpha = self._read_alpha_mask(src, valid_bands, window, data, alpha_mode)
            mark("alpha")
            if not np.any(alpha):
                return None

            d_min = float(np.min(data))
            d_max = float(np.max(data))

            num_bands = len(valid_bands)
            if d_min >= 0.0 and d_max <= 1.0 and self._is_binary_tile(data):
                mins = np.zeros(num_bands, dtype=np.float32)
                maxs = np.ones(num_bands, dtype=np.float32)
            elif d_min >= -1.0001 and d_max <= 1.0001:
                mins = np.full(num_bands, -1.0, dtype=np.float32)
                maxs = np.full(num_bands, 1.0, dtype=np.float32)
            else:
                mins, maxs = self._stats_manager.get_stretch_params(
                    data,
                    valid_bands,
                    src,
                    stats,
                )
            mark("stats")

            if HAS_FAST_TILER:
                tile = render_tile(data, mins, maxs)
            elif fast_stretch_and_stack:
                tile = fast_stretch_and_stack(data, mins, maxs)
            else:
                tile = self._fallback_process(data, mins, maxs)

            tile[:, :, 3] = alpha
            tile_result = tile
            mark("render")
            return tile_result
        except Exception:
            logger.exception(
                "Tile engine failed file=%s z=%s x=%s y=%s bands=%s",
                self.file_path,
                z,
                x,
                y,
                bands,
            )
            return None
        finally:
            if src is not None and close_src and not getattr(src, "closed", False):
                src.close()
            if profile:
                total_ms = (time.perf_counter() - total_start) * 1000.0
                logger.info(
                    "tile_profile file=%s z=%s x=%s y=%s bands=%s alpha_mode=%s "
                    "source=%.2fms window=%.2fms read=%.2fms alpha=%.2fms "
                    "stats=%.2fms render=%.2fms total=%.2fms empty=%s",
                    self.file_path,
                    z,
                    x,
                    y,
                    bands,
                    alpha_mode,
                    timings.get("source", 0.0),
                    timings.get("window", 0.0),
                    timings.get("read", 0.0),
                    timings.get("alpha", 0.0),
                    timings.get("stats", 0.0),
                    timings.get("render", 0.0),
                    total_ms,
                    tile_result is None,
                )

    @staticmethod
    def _is_binary_tile(data):
        return bool(np.count_nonzero((data != 0) & (data != 1)) == 0)

    def _select_resampling(self, src, band, window):
        mode = _resampling_mode()
        if mode == "nearest":
            return Resampling.nearest
        if mode == "bilinear":
            return Resampling.bilinear

        if window is None:
            return Resampling.bilinear

        x_decimation = abs(window.width) / settings.TILE_SIZE
        y_decimation = abs(window.height) / settings.TILE_SIZE
        decimation = max(x_decimation, y_decimation)
        if mode == "fast" and decimation >= 4.0:
            return Resampling.nearest
        if decimation < 2.0:
            return Resampling.bilinear

        try:
            if src.overviews(band):
                return Resampling.bilinear
        except Exception:
            pass

        return Resampling.nearest

    def _read_alpha_mask(self, src, valid_bands, window, data, alpha_mode="auto"):
        if alpha_mode == "data":
            return self._alpha_from_data(data, getattr(src, "nodata", None))

        if not self._has_explicit_mask(src):
            alpha = self._alpha_from_window(src, window, data.shape[1], data.shape[2])
            alpha = self._remove_edge_fill_pixels(data, alpha)
            return alpha

        try:
            masks = src.read_masks(
                valid_bands,
                window=window,
                out_shape=(len(valid_bands), settings.TILE_SIZE, settings.TILE_SIZE),
                boundless=True,
                resampling=Resampling.nearest,
            )
            if masks.ndim == 2:
                alpha = masks
            else:
                alpha = np.max(masks, axis=0)
            alpha = np.where(alpha > 0, 255, 0).astype(np.uint8)
            return alpha
        except Exception:
            logger.warning(
                "Failed to read alpha mask for %s; falling back to data-derived alpha",
                self.file_path,
            )
            return self._alpha_from_data(data, getattr(src, "nodata", None))

    @staticmethod
    def _alpha_from_data(data, nodata=None):
        valid_data = data != 0
        if nodata is not None:
            valid_data &= data != nodata
        valid = np.any(valid_data, axis=0)
        return valid.astype(np.uint8) * 255

    @staticmethod
    def _alpha_from_window(src, window, height, width):
        if window is None or window.width <= 0 or window.height <= 0:
            return np.full((height, width), 255, dtype=np.uint8)

        col_scale = window.width / width
        row_scale = window.height / height
        cols_start = window.col_off + np.arange(width, dtype=np.float64) * col_scale
        cols_end = cols_start + col_scale
        rows_start = window.row_off + np.arange(height, dtype=np.float64) * row_scale
        rows_end = rows_start + row_scale

        cols_inside = (cols_end > 0) & (cols_start < src.width)
        rows_inside = (rows_end > 0) & (rows_start < src.height)
        return (rows_inside[:, None] & cols_inside[None, :]).astype(np.uint8) * 255

    @staticmethod
    def _has_explicit_mask(src):
        if getattr(src, "nodata", None) is not None:
            return True

        mask_flags = getattr(src, "mask_flag_enums", None)
        if not mask_flags:
            return False

        for band_flags in mask_flags:
            for flag in band_flags:
                name = getattr(flag, "name", str(flag)).lower()
                if name in {"alpha", "nodata", "per_dataset"}:
                    return True
        return False

    @staticmethod
    def _remove_edge_fill_pixels(data, alpha):
        fill_pixels = np.all(data == 0, axis=0)
        if not np.any(fill_pixels):
            return alpha
        if np.all(fill_pixels):
            return np.zeros_like(alpha, dtype=np.uint8)

        seeds = fill_pixels & (alpha == 0)
        if not np.any(seeds):
            seeds = np.zeros_like(fill_pixels, dtype=bool)
            seeds[0, :] = fill_pixels[0, :]
            seeds[-1, :] = fill_pixels[-1, :]
            seeds[:, 0] |= fill_pixels[:, 0]
            seeds[:, -1] |= fill_pixels[:, -1]

        if not np.any(seeds):
            return alpha

        if scipy_ndimage is not None:
            outside_fill = scipy_ndimage.binary_propagation(seeds, mask=fill_pixels)
        else:
            outside_fill = seeds
            while True:
                expanded = outside_fill.copy()
                expanded[1:, :] |= outside_fill[:-1, :]
                expanded[:-1, :] |= outside_fill[1:, :]
                expanded[:, 1:] |= outside_fill[:, :-1]
                expanded[:, :-1] |= outside_fill[:, 1:]
                expanded &= fill_pixels
                if np.array_equal(expanded, outside_fill):
                    break
                outside_fill = expanded

        if np.any(outside_fill):
            alpha = alpha.copy()
            alpha[outside_fill] = 0
        return alpha

    def _fallback_process(self, data, mins, maxs):
        count, height, width = data.shape
        out = np.empty((height, width, 4), dtype=np.uint8)
        work = np.empty((height, width), dtype=np.float32)

        channel_count = min(count, 3)
        for channel in range(channel_count):
            low = float(mins[channel])
            high = float(maxs[channel])
            scale = 255.0 / (high - low) if high > low else 0.0

            np.subtract(data[channel], low, out=work)
            np.multiply(work, scale, out=work)
            np.clip(work, 0, 255, out=work)
            out[:, :, channel] = work

        if count == 1:
            out[:, :, 1] = out[:, :, 0]
            out[:, :, 2] = out[:, :, 0]
        elif count == 2:
            out[:, :, 2] = 0

        out[:, :, 3] = self._alpha_from_data(data)
        return out

    def close(self):
        with self._lock:
            if self._src is not None and not self._src.closed:
                self._src.close()
            self._src = None
            self._transformer = None
            self._transformer_key = None
        state = getattr(self._thread_local, "src_state", None)
        if state is not None:
            src = state.get("src")
            if src is not None and not getattr(src, "closed", False):
                src.close()
            self._thread_local.src_state = None

    def __del__(self):
        self.close()
