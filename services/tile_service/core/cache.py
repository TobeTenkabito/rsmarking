<<<<<<< HEAD
import os
from typing import Optional, Any
from cachetools import LRUCache
from diskcache import Cache
from .config import settings


class TileCache:
    def __init__(self, l1_size: int = 1024, l2_dir: str = "cache_data", l2_limit: int = 10 * 1024 ** 3):
        self.l1_cache = LRUCache(maxsize=l1_size)
        self.l2_cache = Cache(l2_dir, size_limit=l2_limit)

    def _make_key(self, index_id: str, z: int, x: int, y: int, bands: str) -> str:
        return f"{index_id}/{z}/{x}/{y}/{bands}"

    def get_tile(self, index_id: str, z: int, x: int, y: int, bands: str) -> Optional[bytes]:
        key = self._make_key(index_id, z, x, y, bands)
        tile = self.l1_cache.get(key)
        if tile is not None:
            return tile
        tile = self.l2_cache.get(key)
        if tile is not None:
            self.l1_cache[key] = tile
            return tile

        return None

    def set_tile(self, index_id: str, z: int, x: int, y: int, bands: str, data: bytes):
        if data is None:
            return
        key = self._make_key(index_id, z, x, y, bands)
        self.l1_cache[key] = data
        self.l2_cache.set(key, data)

    def clear_l1(self):
        self.l1_cache.clear()


tile_cache = TileCache()
=======
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
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
