import io
import os
import logging
import traceback
import rasterio
import mercantile
from fastapi import APIRouter, HTTPException, Response, Depends
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from sqlalchemy import text
from services.tile_service.core.config import settings
from services.tile_service.engine.tiler import TileEngine
from services.data_service.database import get_db
import services.tile_service.logic as logic

logger = logging.getLogger("tile_service.control")
router = APIRouter()


@router.get("/tile/{index_id}/{z}/{x}/{y}.png")
async def get_tile(
        index_id: str, z: int, x: int, y: int,
        bands: str = settings.DEFAULT_BANDS,
        db: AsyncSession = Depends(get_db)
):
    file_path = await logic.get_raster_path(db, index_id)
    if not file_path or not os.path.exists(file_path):
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return Response(content=buf.getvalue(), media_type="image/png")
    try:
        engine = TileEngine(file_path)
        requested_bands = [int(b) for b in bands.split(",")]
        global_stats = {"low": [0, 0, 0], "high": [6000, 6000, 6000]}
        tile_data = engine.read_tile(x, y, z, bands=requested_bands, stats=global_stats)

        if tile_data is None:
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        else:
            img = Image.fromarray(tile_data)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return Response(content=buf.getvalue(), media_type="image/png")

    except Exception as e:
        logger.error(f"瓦片生成失败: {index_id}, Z={z}, X={x}, Y={y}")
        logger.error(traceback.format_exc())
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
            window = from_bounds(tile_bounds.left, tile_bounds.bottom, tile_bounds.right, tile_bounds.top,
                                 src.transform)
            band_indices = list(range(1, min(3, src.count) + 1))
            tile_data = src.read(
                band_indices,
                window=window,
                out_shape=(len(band_indices), 256, 256),
                resampling=Resampling.bilinear,
                boundless=True
            )
            img_rgba = logic.process_tile_pixels_fallback(tile_data)
            img = Image.fromarray(img_rgba)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as e:
        logger.error(f"Debug render failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
