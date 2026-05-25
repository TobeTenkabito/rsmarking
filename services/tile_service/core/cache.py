import hashlib
import json
import logging
import os
from threading import RLock
from typing import Optional

from cachetools import LRUCache
from diskcache import Cache

from .config import settings

logger = logging.getLogger("tile_service.cache")


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
        self._l1_lock = RLock()
        self._l2_init_lock = RLock()
        self._lock = self._l1_lock

    def _get_l2_cache(self):
        if self._l2_cache is None:
            with self._l2_init_lock:
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

    @staticmethod
    def _profile_enabled() -> bool:
        return bool(getattr(settings, "TILE_PROFILE", False)) or os.getenv("TILE_PROFILE") == "1"

    def _log_profile_event(self, event: str, key: str, data: Optional[bytes] = None):
        if not self._profile_enabled():
            return
        key_hash = hashlib.md5(key.encode()).hexdigest()[:12]
        logger.info(
            "tile_cache_profile event=%s key=%s bytes=%s",
            event,
            key_hash,
            len(data) if data is not None else 0,
        )

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

        with self._l1_lock:
            tile = self.l1_cache.get(key)
            if tile is not None:
                self._log_profile_event("l1_hit", key, tile)
                return tile

        tile = self._get_l2_cache().get(key)
        if tile is not None:
            with self._l1_lock:
                self.l1_cache[key] = tile
            self._log_profile_event("l2_hit", key, tile)
            return tile

        self._log_profile_event("miss", key)
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
        with self._l1_lock:
            self.l1_cache[key] = data
        self._get_l2_cache().set(key, data)
        self._log_profile_event("set", key, data)

    def clear_l1(self):
        with self._l1_lock:
            self.l1_cache.clear()

    def clear(self):
        with self._l1_lock:
            self.l1_cache.clear()
        with self._l2_init_lock:
            l2_cache = self._l2_cache
        if l2_cache is not None:
            l2_cache.clear()


tile_cache = TileCache(
    l1_size=settings.CACHE_L1_SIZE,
    l2_dir=settings.CACHE_L2_DIR,
    l2_limit=settings.CACHE_L2_SIZE_LIMIT,
)
