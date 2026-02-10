import os
import hashlib
from typing import Optional
from cachetools import LRUCache
from diskcache import Cache
from .config import settings


class TileCache:
    def __init__(self):
        self.l1_cache = LRUCache(maxsize=settings.CACHE_L1_SIZE)
        self.l2_cache = Cache(
            settings.CACHE_L2_DIR,
            size_limit=settings.CACHE_L2_SIZE_LIMIT
        )
    def _generate_key(self, index_id: str, z: int, x: int, y: int, bands: str) -> str:
        raw_key = f"{index_id}:{z}:{x}:{y}:{bands}"
        return hashlib.md5(raw_key.encode()).hexdigest()

    def get_tile(self, index_id: str, z: int, x: int, y: int, bands: str) -> Optional[bytes]:
        key = self._generate_key(index_id, z, x, y, bands)
        tile = self.l1_cache.get(key)
        if tile is not None:
            return tile
        tile = self.l2_cache.get(key)
        if tile is not None:
            self.l1_cache[key] = tile
            return tile
        return None

    def set_tile(self, index_id: str, z: int, x: int, y: int, bands: str, data: bytes):
        key = self._generate_key(index_id, z, x, y, bands)
        self.l1_cache[key] = data
        self.l2_cache.set(key, data)


tile_cache = TileCache()
