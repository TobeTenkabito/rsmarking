import hashlib
import json
from typing import Optional
from cachetools import LRUCache
from diskcache import Cache
from .config import settings


class TileCache:
    def __init__(
        self,
        l1_size: int = 1024,
        l2_dir: str = "cache_data",
        l2_limit: int = 10 * 1024 ** 3,
    ):
        self.l1_cache = LRUCache(maxsize=l1_size)
        self.l2_cache = Cache(l2_dir, size_limit=l2_limit)

    def _make_key(
        self,
        index_id: str,
        z: int,
        x: int,
        y: int,
        bands: str,
        stats: Optional[dict] = None,
    ) -> str:
        base = f"{index_id}/{z}/{x}/{y}/{bands}"
        if not stats:
            return base
        # 对 stats dict 做稳定哈希（排序后 JSON → md5 前 8 位）
        stats_str = json.dumps(stats, sort_keys=True, separators=(',', ':'))
        stats_hash = hashlib.md5(stats_str.encode()).hexdigest()[:8]
        return f"{base}/{stats_hash}"

    def get_tile(
        self,
        index_id: str,
        z: int,
        x: int,
        y: int,
        bands: str,
        stats: Optional[dict] = None,
    ) -> Optional[bytes]:
        key = self._make_key(index_id, z, x, y, bands, stats)

        tile = self.l1_cache.get(key)
        if tile is not None:
            return tile

        tile = self.l2_cache.get(key)
        if tile is not None:
            self.l1_cache[key] = tile  # 回填 L1
            return tile

        return None

    def set_tile(
        self,
        index_id: str,
        z: int,
        x: int,
        y: int,
        bands: str,
        data: bytes,
        stats: Optional[dict] = None,
    ):
        if data is None:
            return
        key = self._make_key(index_id, z, x, y, bands, stats)
        self.l1_cache[key] = data
        self.l2_cache.set(key, data)

    def clear_l1(self):
        self.l1_cache.clear()


tile_cache = TileCache()
