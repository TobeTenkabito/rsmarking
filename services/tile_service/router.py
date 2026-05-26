import io
import logging
import os
import time
from functools import lru_cache

import mercantile
import rasterio
from fastapi import APIRouter, Depends, HTTPException, Response
from PIL import Image
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
from services.tile_service.core.cache import tile_cache
from services.tile_service.core.config import settings
from services.tile_service.engine.tiler import get_tile_engine

import services.tile_service.logic as logic

logger = logging.getLogger("tile_service.control")
router = APIRouter()

RENDER_CACHE_VERSION = "render_v3"


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


def _png_response(content: bytes, status_code: int = 200) -> Response:
    return Response(content=content, media_type="image/png", status_code=status_code)


def _encode_png(tile_data) -> bytes:
    if tile_data is None:
        return _empty_png_bytes()

    img = Image.fromarray(tile_data)
    buf = io.BytesIO()
    img.save(buf, **_png_save_options())
    return buf.getvalue()


def _parse_bands(bands: str):
    parsed = []
    for part in (bands or settings.DEFAULT_BANDS).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            parsed.append(int(part))
        except ValueError:
            logger.warning("Ignoring invalid band value: %s", part)

    return parsed or [int(part) for part in settings.DEFAULT_BANDS.split(",")]


def _file_version(file_path: str) -> int:
    try:
        return os.stat(file_path).st_mtime_ns
    except OSError:
        return 0


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


@router.get("/tile/{index_id}/{z}/{x}/{y}.png")
async def get_tile(
    index_id: str,
    z: int,
    x: int,
    y: int,
    bands: str = settings.DEFAULT_BANDS,
    db: AsyncSession = Depends(get_db),
):
    profile = _profile_enabled()
    total_start = time.perf_counter()
    timings = {
        "db_path": 0.0,
        "file_stat": 0.0,
        "cache_get": 0.0,
        "engine_read": 0.0,
        "png_encode": 0.0,
        "cache_set": 0.0,
    }
    cache_hit = False
    response_len = 0
    file_version = 0
    file_path = None
    alpha_strategy = _alpha_strategy()
    render_options = _render_options()

    try:
        start = time.perf_counter()
        file_path = await logic.get_raster_path(db, index_id)
        timings["db_path"] = (time.perf_counter() - start) * 1000.0

        start = time.perf_counter()
        file_exists = bool(file_path and os.path.exists(file_path))
        if file_exists:
            file_version = _file_version(file_path)
        timings["file_stat"] = (time.perf_counter() - start) * 1000.0

        if not file_exists:
            content = _empty_png_bytes()
            response_len = len(content)
            return _png_response(content)

        requested_bands = _parse_bands(bands)
        band_key = ",".join(str(b) for b in requested_bands)

        start = time.perf_counter()
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
        timings["cache_get"] = (time.perf_counter() - start) * 1000.0
        if cached_tile is not None:
            cache_hit = True
            response_len = len(cached_tile)
            return _png_response(cached_tile)

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
        response_len = len(content)

        start = time.perf_counter()
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
        timings["cache_set"] = (time.perf_counter() - start) * 1000.0
        return _png_response(content)

    except Exception:
        logger.exception("Tile generation failed: %s, Z=%s, X=%s, Y=%s", index_id, z, x, y)
        return Response(status_code=500)
    finally:
        if profile:
            total_ms = (time.perf_counter() - total_start) * 1000.0
            logger.info(
                "tile_route_profile index=%s z=%s x=%s y=%s bands=%s "
                "db_path=%.2fms file_stat=%.2fms cache_get=%.2fms "
                "engine=%.2fms encode=%.2fms cache_set=%.2fms total=%.2fms "
                "cache_hit=%s bytes=%s alpha=%s renderer=%s file_version=%s path=%s",
                index_id,
                z,
                x,
                y,
                bands,
                timings["db_path"],
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
            return _png_response(_encode_png(img_rgba))
    except Exception as e:
        logger.exception("Debug render failed")
        raise HTTPException(status_code=500, detail=str(e))
