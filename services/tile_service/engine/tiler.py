from collections import OrderedDict
import os
from threading import RLock

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling

from services.tile_service.core.config import settings

from .stats import StatsManager
from .utils import get_tile_window


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


class TileEngine:
    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self._src = None
        self._stats_manager = StatsManager()
        self._transformer = None
        self._file_mtime_ns = None
        self._crs_wgs84 = "EPSG:4326"
        self._lock = RLock()

    def _get_src(self):
        current_mtime_ns = _file_mtime_ns(self.file_path)
        file_changed = (
            self._file_mtime_ns is not None
            and current_mtime_ns != self._file_mtime_ns
        )

        if self._src is None or self._src.closed or file_changed:
            if self._src is not None and not self._src.closed:
                self._src.close()

            if file_changed:
                StatsManager.invalidate_file(self.file_path)

            self._src = rasterio.open(self.file_path)
            self._transformer = Transformer.from_crs(
                self._crs_wgs84,
                self._src.crs,
                always_xy=True,
            )
            self._stats_manager.clear()
            self._file_mtime_ns = current_mtime_ns

        return self._src

    def read_tile(self, x: int, y: int, z: int, bands: list = None, stats: dict = None):
        if not os.path.exists(self.file_path):
            with self._lock:
                self.close()
            return None

        with self._lock:
            try:
                src = self._get_src()
                valid_bands = bands if bands else list(range(1, min(4, src.count) + 1))
                valid_bands = [b for b in valid_bands if 1 <= b <= src.count] or [1]
                window = get_tile_window(x, y, z, src, self._transformer)
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

                alpha = self._read_alpha_mask(src, valid_bands, window, data)
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

                if HAS_FAST_TILER:
                    tile = render_tile(data, mins, maxs)
                elif fast_stretch_and_stack:
                    tile = fast_stretch_and_stack(data, mins, maxs)
                else:
                    tile = self._fallback_process(data, mins, maxs)

                tile[:, :, 3] = alpha
                return tile
            except Exception as e:
                print(f"### [TILE_ENGINE_ERROR] {e} ###")
                return None

    @staticmethod
    def _is_binary_tile(data):
        return bool(np.count_nonzero((data != 0) & (data != 1)) == 0)

    def _select_resampling(self, src, band, window):
        if window is None:
            return Resampling.bilinear

        x_decimation = abs(window.width) / settings.TILE_SIZE
        y_decimation = abs(window.height) / settings.TILE_SIZE
        decimation = max(x_decimation, y_decimation)
        if decimation < 2.0:
            return Resampling.bilinear

        try:
            if src.overviews(band):
                return Resampling.bilinear
        except Exception:
            pass

        return Resampling.nearest

    def _read_alpha_mask(self, src, valid_bands, window, data):
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
            return self._alpha_from_data(data)

    @staticmethod
    def _alpha_from_data(data):
        return (np.any(data != 0, axis=0).astype(np.uint8) * 255)

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

    def __del__(self):
        self.close()
