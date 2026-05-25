import logging
import os

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("tile_service.logic")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")


def resolve_raster_path(file_path: str | None, cog_path: str | None = None) -> str | None:
    candidates = []
    if cog_path:
        candidates.extend(_expand_path_candidates(cog_path, prefer_cog=True))
    if file_path:
        candidates.extend(_expand_path_candidates(file_path, prefer_cog=False))

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _expand_path_candidates(path: str, prefer_cog: bool):
    if not path:
        return []

    candidates = []
    if os.path.isabs(path) and not path.startswith("/data/"):
        candidates.append(path)

    normalized = path.replace("\\", "/")
    if normalized.startswith("/data/") or prefer_cog:
        candidates.append(os.path.join(COG_DIR, os.path.basename(normalized)))

    candidates.append(path)
    return candidates


async def get_raster_path(db: AsyncSession, index_id: str) -> str:
    try:
        try:
            val = int(index_id)
        except ValueError:
            val = index_id

        query = text("SELECT file_path, cog_path FROM raster_metadata WHERE index_id = :val OR id = :val")
        result = await db.execute(query, {"val": val})
        row = result.one_or_none()
        if row:
            return resolve_raster_path(row[0], row[1])

        logger.warning("Raster record not found for: %s", index_id)
        return None
    except Exception:
        logger.exception("Database query error for %s", index_id)
        return None


def process_tile_pixels_fallback(data: np.ndarray) -> np.ndarray:
    """Deprecated debug-only fallback renderer kept for /debug/render-first.png."""
    data = np.asarray(data, dtype=np.float32)
    count, height, width = data.shape
    out = np.zeros((height, width, 4), dtype=np.uint8)
    if count == 0:
        return out

    channel_count = min(count, 3)
    work = np.empty((height, width), dtype=np.float32)
    for channel in range(channel_count):
        band = data[channel]
        valid = band[band != 0]
        if valid.size >= 10:
            b_min, b_max = np.percentile(valid, [2, 98])
        else:
            b_min, b_max = float(np.min(band)), float(np.max(band))

        if b_max > b_min:
            np.subtract(band, b_min, out=work)
            np.multiply(work, 255.0 / (b_max - b_min), out=work)
            np.clip(work, 0, 255, out=work)
            out[:, :, channel] = work

    if count == 1:
        out[:, :, 1] = out[:, :, 0]
        out[:, :, 2] = out[:, :, 0]

    alpha = data[0] != 0
    for channel in range(1, count):
        np.logical_or(alpha, data[channel] != 0, out=alpha)
    out[:, :, 3] = alpha
    out[:, :, 3] *= 255
    return out
