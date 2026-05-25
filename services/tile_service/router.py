import io
import logging
import os
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

RENDER_CACHE_VERSION = "render_v2"
PNG_SAVE_OPTIONS = {"format": "PNG", "compress_level": 1}


@lru_cache(maxsize=1)
def _empty_png_bytes() -> bytes:
    img = Image.new("RGBA", (settings.TILE_SIZE, settings.TILE_SIZE), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, **PNG_SAVE_OPTIONS)
    return buf.getvalue()


def _png_response(content: bytes, status_code: int = 200) -> Response:
    return Response(content=content, media_type="image/png", status_code=status_code)


def _encode_png(tile_data) -> bytes:
    if tile_data is None:
        return _empty_png_bytes()

    img = Image.fromarray(tile_data)
    buf = io.BytesIO()
    img.save(buf, **PNG_SAVE_OPTIONS)
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


@router.get("/tile/{index_id}/{z}/{x}/{y}.png")
async def get_tile(
    index_id: str,
    z: int,
    x: int,
    y: int,
    bands: str = settings.DEFAULT_BANDS,
    db: AsyncSession = Depends(get_db),
):
    file_path = await logic.get_raster_path(db, index_id)
    if not file_path or not os.path.exists(file_path):
        return _png_response(_empty_png_bytes())

    requested_bands = _parse_bands(bands)
    band_key = ",".join(str(b) for b in requested_bands)
    file_version = _file_version(file_path)
    alpha_strategy = _alpha_strategy()

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
    )
    if cached_tile is not None:
        return _png_response(cached_tile)

    try:
        engine = get_tile_engine(file_path)
        tile_data = engine.read_tile(
            x,
            y,
            z,
            bands=requested_bands,
        )
        content = _encode_png(tile_data)
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
        )
        return _png_response(content)

    except Exception:
        logger.exception("Tile generation failed: %s, Z=%s, X=%s, Y=%s", index_id, z, x, y)
        return Response(status_code=500)


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
