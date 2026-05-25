import hashlib
import json
from threading import RLock
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
        self.l2_dir = l2_dir
        self.l2_limit = l2_limit
        self._l2_cache = None
        self._lock = RLock()

    def _get_l2_cache(self):
        if self._l2_cache is None:
            self._l2_cache = Cache(self.l2_dir, size_limit=self.l2_limit)
        return self._l2_cache

    def _make_key(
        self,
        index_id: str,
        z: int,
        x: int,
        y: int,
        bands: str,
        stats: Optional[dict] = None,
        *,
        file_version: Optional[int | str] = None,
        tile_size: Optional[int] = None,
        renderer_version: Optional[str] = None,
        alpha_strategy: Optional[str] = None,
        style_hash: Optional[str] = None,
        render_options: Optional[dict] = None,
    ) -> str:
        base = f"{index_id}/{z}/{x}/{y}/{bands}"
        parts = [base]

        if stats:
            parts.append(self._hash_mapping(stats))
        if file_version is not None:
            parts.append(f"file:{file_version}")
        if tile_size is not None:
            parts.append(f"size:{tile_size}")
        if renderer_version:
            parts.append(f"renderer:{renderer_version}")
        if alpha_strategy:
            parts.append(f"alpha:{alpha_strategy}")
        if style_hash:
            parts.append(f"style:{style_hash}")
        if render_options:
            parts.append(f"options:{self._hash_mapping(render_options)}")

        return "/".join(parts)

    @staticmethod
    def _hash_mapping(value: dict) -> str:
        value_str = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.md5(value_str.encode()).hexdigest()[:8]

    def get_tile(
        self,
        index_id: str,
        z: int,
        x: int,
        y: int,
        bands: str,
        stats: Optional[dict] = None,
        *,
        file_version: Optional[int | str] = None,
        tile_size: Optional[int] = None,
        renderer_version: Optional[str] = None,
        alpha_strategy: Optional[str] = None,
        style_hash: Optional[str] = None,
        render_options: Optional[dict] = None,
    ) -> Optional[bytes]:
        key = self._make_key(
            index_id,
            z,
            x,
            y,
            bands,
            stats,
            file_version=file_version,
            tile_size=tile_size,
            renderer_version=renderer_version,
            alpha_strategy=alpha_strategy,
            style_hash=style_hash,
            render_options=render_options,
        )

        with self._lock:
            tile = self.l1_cache.get(key)
            if tile is not None:
                return tile

            tile = self._get_l2_cache().get(key)
            if tile is not None:
                self.l1_cache[key] = tile
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
        *,
        file_version: Optional[int | str] = None,
        tile_size: Optional[int] = None,
        renderer_version: Optional[str] = None,
        alpha_strategy: Optional[str] = None,
        style_hash: Optional[str] = None,
        render_options: Optional[dict] = None,
    ):
        if data is None:
            return
        if not isinstance(data, bytes):
            data = bytes(data)

        key = self._make_key(
            index_id,
            z,
            x,
            y,
            bands,
            stats,
            file_version=file_version,
            tile_size=tile_size,
            renderer_version=renderer_version,
            alpha_strategy=alpha_strategy,
            style_hash=style_hash,
            render_options=render_options,
        )
        with self._lock:
            self.l1_cache[key] = data
            self._get_l2_cache().set(key, data)

    def clear_l1(self):
        with self._lock:
            self.l1_cache.clear()

    def clear(self):
        with self._lock:
            self.l1_cache.clear()
            if self._l2_cache is not None:
                self._l2_cache.clear()


tile_cache = TileCache(
    l1_size=settings.CACHE_L1_SIZE,
    l2_dir=settings.CACHE_L2_DIR,
    l2_limit=settings.CACHE_L2_SIZE_LIMIT,
)
