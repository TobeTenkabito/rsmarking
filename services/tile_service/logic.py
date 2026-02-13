import logging
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("tile_service.logic")


async def get_raster_path(db: AsyncSession, index_id: str) -> str:
    try:
        try:
            val = int(index_id)
        except ValueError:
            val = index_id
        query = text("SELECT file_path FROM raster_metadata WHERE index_id = :val OR id = :val")
        result = await db.execute(query, {"val": val})
        row = result.one_or_none()

        if row:
            return row[0]
        else:
            logger.warning(f"Raster record not found for: {index_id}")
            return None
    except Exception as e:
        logger.error(f"Database query error for {index_id}: {e}")
        return None


def process_tile_pixels_fallback(data: np.ndarray) -> np.ndarray:
    count, height, width = data.shape
    processed = []
    for i in range(count):
        band = data[i].astype(np.float32)
        b_min, b_max = np.percentile(band, [2, 98])
        if b_max > b_min:
            stretched = (band - b_min) / (b_max - b_min) * 255
            processed.append(np.clip(stretched, 0, 255).astype(np.uint8))
        else:
            processed.append(np.zeros((height, width), dtype=np.uint8))
    if count >= 3:
        rgb = np.stack(processed[:3], axis=-1)
    elif count > 0:
        rgb = np.stack([processed[0]] * 3, axis=-1)
    else:
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
    alpha = np.where(np.max(data, axis=0) > 0, 255, 0).astype(np.uint8)

    return np.dstack([rgb, alpha])
