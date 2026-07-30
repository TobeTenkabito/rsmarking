from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import io
import logging
import os
from threading import Lock, RLock
import time

import mercantile
import rasterio
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from PIL import Image
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from services.data_service.database import get_db
from services.tile_service.core.cache import tile_cache
from services.tile_service.core.config import settings
from services.tile_service.engine.tiler import get_tile_engine
from functions.implement.raster_validity import raster_validity_signature

import services.tile_service.logic as logic

logger = logging.getLogger("tile_service.control")
router = APIRouter()

RENDER_CACHE_VERSION = "render_v5_mask_propagation"


@dataclass
class _RenderLockEntry:
    lock: Lock = field(default_factory=Lock)
    references: int = 0


class _KeyedRenderLocks:
    """Bounded-lifetime locks that collapse identical concurrent tile misses."""

    def __init__(self):
        self._guard = RLock()
        self._entries: dict[str, _RenderLockEntry] = {}

    @contextmanager
    def hold(self, key: str):
        with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _RenderLockEntry()
                self._entries[key] = entry
            entry.references += 1

        entry.lock.acquire()
        try:
            yield
        finally:
            entry.lock.release()
            with self._guard:
                entry.references -= 1
                if entry.references == 0:
                    self._entries.pop(key, None)


@dataclass
class _TileRenderResult:
    content: bytes
    file_version: str | None
    cache_hit: bool
    missing_source: bool
    timings: dict[str, float]


_TILE_RENDER_LOCKS = _KeyedRenderLocks()


def _profile_enabled() -> bool:
    return bool(getattr(settings, "TILE_PROFILE", False)) or os.getenv("TILE_PROFILE") == "1"


def _png_compress_level() -> int:
    level = int(getattr(settings, "TILE_PNG_COMPRESS_LEVEL", 1) or 0)
    return min(9, max(0, level))


def _png_save_options() -> dict:
    return {"format": "PNG", "compress_level": _png_compress_level()}


@lru_cache(maxsize=1)
def _empty_png_bytes() -> bytes:
    img = Image.new("RGBA", (settings.TILE_SIZE, settings.TILE_SIZE), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, **_png_save_options())
    return buf.getvalue()


def _png_response(
    content: bytes,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> Response:
    return Response(
        content=content,
        media_type="image/png",
        status_code=status_code,
        headers=headers,
    )


def _encode_png(tile_data) -> bytes:
    if tile_data is None:
        return _empty_png_bytes()

    img = Image.fromarray(tile_data)
    buf = io.BytesIO()
    img.save(buf, **_png_save_options())
    return buf.getvalue()


def _parse_bands(bands: str):
    parsed = []
    seen = set()
    max_bands = max(1, int(getattr(settings, "TILE_MAX_BANDS", 4) or 4))
    raw_bands = bands if isinstance(bands, str) else settings.DEFAULT_BANDS
    if len(raw_bands) > 128:
        raise HTTPException(status_code=400, detail="Band selection is too long")

    for part in (raw_bands or settings.DEFAULT_BANDS).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            band = int(part)
        except ValueError:
            logger.warning("Ignoring invalid band value: %s", part)
            continue
        if band < 1 or band in seen:
            continue
        seen.add(band)
        parsed.append(band)
        if len(parsed) >= max_bands:
            break

    return parsed or [int(part) for part in settings.DEFAULT_BANDS.split(",")]


def _file_version(file_path: str) -> str:
    return raster_validity_signature(file_path)


def _alpha_strategy() -> str:
    mode = str(getattr(settings, "TILE_ALPHA_MODE", "auto") or "auto").lower()
    if mode not in {"auto", "data"}:
        mode = "auto"
    return f"mask_{mode}"


def _resampling_mode() -> str:
    mode = str(getattr(settings, "TILE_RESAMPLING_MODE", "quality") or "quality").lower()
    if mode not in {"quality", "fast", "nearest", "bilinear"}:
        mode = "quality"
    return mode


def _render_options() -> dict:
    return {
        "resampling": _resampling_mode(),
        "png_compress": _png_compress_level(),
    }


def _safe_basename(file_path: str | None) -> str:
    if not file_path:
        return ""
    return os.path.basename(file_path)


def _validate_tile_coordinates(z: int, x: int, y: int) -> None:
    max_zoom = max(0, int(getattr(settings, "TILE_MAX_ZOOM", 24) or 24))
    if z < 0 or z > max_zoom:
        raise HTTPException(
            status_code=400,
            detail=f"Zoom must be between 0 and {max_zoom}",
        )
    axis_size = 1 << z
    if x < 0 or y < 0 or x >= axis_size or y >= axis_size:
        raise HTTPException(
            status_code=400,
            detail="Tile coordinates are outside the requested zoom level",
        )


def _render_lock_key(
    file_path: str | None,
    index_id: str,
    z: int,
    x: int,
    y: int,
    band_key: str,
) -> str:
    return "\0".join(
        (str(file_path or ""), str(index_id), str(z), str(x), str(y), band_key)
    )


def _render_tile_sync(
    file_path: str | None,
    index_id: str,
    z: int,
    x: int,
    y: int,
    requested_bands: list[int],
    band_key: str,
    alpha_strategy: str,
    render_options: dict,
) -> _TileRenderResult:
    timings = {
        "singleflight_wait": 0.0,
        "file_stat": 0.0,
        "cache_get": 0.0,
        "engine_read": 0.0,
        "png_encode": 0.0,
        "cache_set": 0.0,
    }
    wait_start = time.perf_counter()
    lock_key = _render_lock_key(file_path, index_id, z, x, y, band_key)

    with _TILE_RENDER_LOCKS.hold(lock_key):
        timings["singleflight_wait"] = (time.perf_counter() - wait_start) * 1000.0

        start = time.perf_counter()
        file_exists = bool(file_path and os.path.exists(file_path))
        file_version = _file_version(file_path) if file_exists else None
        timings["file_stat"] = (time.perf_counter() - start) * 1000.0

        if not file_exists:
            return _TileRenderResult(
                content=_empty_png_bytes(),
                file_version=None,
                cache_hit=False,
                missing_source=True,
                timings=timings,
            )

        start = time.perf_counter()
        try:
            cached_tile = tile_cache.get_tile(
                index_id,
                z,
                x,
                y,
                band_key,
                file_version=file_version,
                tile_size=settings.TILE_SIZE,
                renderer_version=RENDER_CACHE_VERSION,
                alpha_strategy=alpha_strategy,
                render_options=render_options,
            )
        except Exception:
            cached_tile = None
            logger.exception("Tile cache read failed; rendering without cache")
        timings["cache_get"] = (time.perf_counter() - start) * 1000.0
        if cached_tile is not None:
            return _TileRenderResult(
                content=cached_tile,
                file_version=file_version,
                cache_hit=True,
                missing_source=False,
                timings=timings,
            )

        engine = get_tile_engine(file_path)
        start = time.perf_counter()
        tile_data = engine.read_tile(
            x,
            y,
            z,
            bands=requested_bands,
        )
        timings["engine_read"] = (time.perf_counter() - start) * 1000.0

        start = time.perf_counter()
        content = _encode_png(tile_data)
        timings["png_encode"] = (time.perf_counter() - start) * 1000.0

        start = time.perf_counter()
        try:
            tile_cache.set_tile(
                index_id,
                z,
                x,
                y,
                band_key,
                content,
                file_version=file_version,
                tile_size=settings.TILE_SIZE,
                renderer_version=RENDER_CACHE_VERSION,
                alpha_strategy=alpha_strategy,
                render_options=render_options,
            )
        except Exception:
            logger.exception("Tile cache write failed; returning rendered tile")
        timings["cache_set"] = (time.perf_counter() - start) * 1000.0
        return _TileRenderResult(
            content=content,
            file_version=file_version,
            cache_hit=False,
            missing_source=False,
            timings=timings,
        )


def _tile_http_headers(
    content: bytes,
    file_version: str | None,
) -> dict[str, str]:
    if file_version is None:
        return {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        }

    etag = hashlib.sha256(content).hexdigest()[:32]
    max_age = max(
        0,
        int(getattr(settings, "TILE_HTTP_CACHE_MAX_AGE_SECONDS", 60) or 0),
    )
    stale = max(
        0,
        int(
            getattr(
                settings,
                "TILE_HTTP_CACHE_STALE_WHILE_REVALIDATE_SECONDS",
                300,
            )
            or 0
        ),
    )
    cache_control = f"public, max-age={max_age}"
    if stale:
        cache_control += f", stale-while-revalidate={stale}"
    return {
        "Cache-Control": cache_control,
        "ETag": f'"{etag}"',
        "X-Content-Type-Options": "nosniff",
    }


def _etag_matches(if_none_match: str | None, etag: str | None) -> bool:
    if not if_none_match or not etag:
        return False
    expected = etag.removeprefix("W/")
    return any(
        candidate.strip().removeprefix("W/") in {"*", expected}
        for candidate in if_none_match.split(",")
    )


@router.get("/tile/{index_id}/{z}/{x}/{y}.png")
async def get_tile(
    index_id: str,
    z: int,
    x: int,
    y: int,
    bands: str = settings.DEFAULT_BANDS,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    db: AsyncSession = Depends(get_db),
):
    profile = _profile_enabled()
    total_start = time.perf_counter()
    timings = {
        "db_path": 0.0,
        "singleflight_wait": 0.0,
        "file_stat": 0.0,
        "cache_get": 0.0,
        "engine_read": 0.0,
        "png_encode": 0.0,
        "cache_set": 0.0,
    }
    cache_hit = False
    response_len = 0
    file_version = None
    file_path = None
    alpha_strategy = _alpha_strategy()
    render_options = _render_options()

    try:
        _validate_tile_coordinates(z, x, y)
        start = time.perf_counter()
        file_path = await logic.get_raster_path(db, index_id)
        timings["db_path"] = (time.perf_counter() - start) * 1000.0

        requested_bands = _parse_bands(bands)
        band_key = ",".join(str(b) for b in requested_bands)
        result = await run_in_threadpool(
            _render_tile_sync,
            file_path,
            index_id,
            z,
            x,
            y,
            requested_bands,
            band_key,
            alpha_strategy,
            render_options,
        )
        timings.update(result.timings)
        cache_hit = result.cache_hit
        file_version = result.file_version
        response_len = len(result.content)
        headers = _tile_http_headers(result.content, file_version)
        request_etag = if_none_match if isinstance(if_none_match, str) else None
        if _etag_matches(request_etag, headers.get("ETag")):
            response_len = 0
            return Response(status_code=304, headers=headers)
        return _png_response(result.content, headers=headers)

    except HTTPException:
        raise
    except Exception:
        logger.exception("Tile generation failed: %s, Z=%s, X=%s, Y=%s", index_id, z, x, y)
        return Response(status_code=500)
    finally:
        if profile:
            total_ms = (time.perf_counter() - total_start) * 1000.0
            logger.info(
                "tile_route_profile index=%s z=%s x=%s y=%s bands=%s "
                "db_path=%.2fms wait=%.2fms file_stat=%.2fms cache_get=%.2fms "
                "engine=%.2fms encode=%.2fms cache_set=%.2fms total=%.2fms "
                "cache_hit=%s bytes=%s alpha=%s renderer=%s file_version=%s path=%s",
                index_id,
                z,
                x,
                y,
                bands,
                timings["db_path"],
                timings["singleflight_wait"],
                timings["file_stat"],
                timings["cache_get"],
                timings["engine_read"],
                timings["png_encode"],
                timings["cache_set"],
                total_ms,
                cache_hit,
                response_len,
                alpha_strategy,
                RENDER_CACHE_VERSION,
                file_version,
                _safe_basename(file_path),
            )


@router.get("/debug/render-first.png")
async def debug_render_first(db: AsyncSession = Depends(get_db)):
    query = text("SELECT index_id, file_path FROM raster_metadata ORDER BY id DESC LIMIT 1")
    result = await db.execute(query)
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No raster records found")

    index_id, file_path = row
    try:
        content = await run_in_threadpool(_render_debug_tile_sync, file_path)
        return _png_response(content, headers={"Cache-Control": "no-store"})
    except Exception as e:
        logger.exception("Debug render failed")
        raise HTTPException(status_code=500, detail=str(e))


def _render_debug_tile_sync(file_path: str) -> bytes:
    z, x, y = 2, 2, 1
    with rasterio.open(file_path) as src:
        tile_bounds = mercantile.xy_bounds(x, y, z)
        window = from_bounds(
            tile_bounds.left,
            tile_bounds.bottom,
            tile_bounds.right,
            tile_bounds.top,
            src.transform,
        )
        band_indices = list(range(1, min(3, src.count) + 1))
        tile_data = src.read(
            band_indices,
            window=window,
            out_shape=(len(band_indices), settings.TILE_SIZE, settings.TILE_SIZE),
            resampling=Resampling.bilinear,
            boundless=True,
        )
        img_rgba = logic.process_tile_pixels_fallback(tile_data)
        return _encode_png(img_rgba)
