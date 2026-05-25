import logging
import os
import time
from collections import OrderedDict
from threading import RLock

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.tile_service.core.config import settings

logger = logging.getLogger("tile_service.logic")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")
_PATH_CACHE = OrderedDict()
_PATH_CACHE_LOCK = RLock()


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
    cache_key = str(index_id)
    cached = _get_cached_raster_path(cache_key)
    if cached is not _CACHE_MISS:
        return cached

    try:
        try:
            val = int(index_id)
        except ValueError:
            val = index_id

        query = text("SELECT file_path, cog_path FROM raster_metadata WHERE index_id = :val OR id = :val")
        result = await db.execute(query, {"val": val})
        row = result.one_or_none()
        if row:
            resolved = resolve_raster_path(row[0], row[1])
            _set_cached_raster_path(cache_key, resolved)
            return resolved

        logger.warning("Raster record not found for: %s", index_id)
        _set_cached_raster_path(cache_key, None)
        return None
    except Exception:
        logger.exception("Database query error for %s", index_id)
        return None


_CACHE_MISS = object()


def _path_cache_ttl() -> float:
    return max(0.0, float(getattr(settings, "TILE_PATH_CACHE_TTL_SECONDS", 30.0) or 0.0))


def _path_cache_maxsize() -> int:
    return max(1, int(getattr(settings, "TILE_PATH_CACHE_MAXSIZE", 1024) or 1024))


def _get_cached_raster_path(index_id: str):
    ttl = _path_cache_ttl()
    if ttl <= 0.0:
        return _CACHE_MISS

    now = time.monotonic()
    with _PATH_CACHE_LOCK:
        entry = _PATH_CACHE.get(index_id)
        if entry is None:
            return _CACHE_MISS

        expires_at, value = entry
        if expires_at <= now:
            _PATH_CACHE.pop(index_id, None)
            return _CACHE_MISS

        _PATH_CACHE.move_to_end(index_id)
        return value


def _set_cached_raster_path(index_id: str, value: str | None):
    ttl = _path_cache_ttl()
    if ttl <= 0.0:
        return

    expires_at = time.monotonic() + ttl
    with _PATH_CACHE_LOCK:
        _PATH_CACHE[index_id] = (expires_at, value)
        _PATH_CACHE.move_to_end(index_id)
        while len(_PATH_CACHE) > _path_cache_maxsize():
            _PATH_CACHE.popitem(last=False)


def clear_raster_path_cache():
    with _PATH_CACHE_LOCK:
        _PATH_CACHE.clear()


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
