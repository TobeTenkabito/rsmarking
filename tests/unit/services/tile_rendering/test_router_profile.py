import asyncio
import logging
from threading import RLock, get_ident
import time

import pytest

pytest.importorskip("diskcache")
pytest.importorskip("fastapi")
pytest.importorskip("rasterio")

from services.tile_service import router as tile_router


class FakeCache:
    def get_tile(self, *args, **kwargs):
        return b"png"

    def set_tile(self, *args, **kwargs):
        raise AssertionError("cache set should not be called on cache hit")


async def _fake_get_raster_path(db, index_id):
    return db["path"]


def test_route_profile_logs_only_when_enabled(tmp_path, monkeypatch, caplog):
    raster_path = tmp_path / "profile.tif"
    raster_path.write_bytes(b"not-a-real-raster")
    monkeypatch.setattr(tile_router.logic, "get_raster_path", _fake_get_raster_path)
    monkeypatch.setattr(tile_router, "tile_cache", FakeCache())
    monkeypatch.setattr(tile_router.settings, "TILE_PROFILE", False)
    monkeypatch.delenv("TILE_PROFILE", raising=False)

    caplog.set_level(logging.INFO, logger="tile_service.control")
    response = asyncio.run(
        tile_router.get_tile("idx", 3, 2, 3, bands="1", db={"path": str(raster_path)})
    )

    assert response.status_code == 200
    assert "tile_route_profile" not in caplog.text

    caplog.clear()
    monkeypatch.setenv("TILE_PROFILE", "1")
    response = asyncio.run(
        tile_router.get_tile("idx", 3, 2, 3, bands="1", db={"path": str(raster_path)})
    )

    assert response.status_code == 200
    assert "tile_route_profile" in caplog.text
    assert "path=profile.tif" in caplog.text


class CoordinatedCache:
    def __init__(self):
        self.value = None
        self.get_calls = 0
        self.set_calls = 0
        self.lock = RLock()

    def get_tile(self, *args, **kwargs):
        with self.lock:
            self.get_calls += 1
            return self.value

    def set_tile(self, *args, **kwargs):
        with self.lock:
            self.set_calls += 1
            self.value = args[5]


class SlowEngine:
    def __init__(self):
        self.calls = 0
        self.thread_ids = []
        self.lock = RLock()

    def read_tile(self, *args, **kwargs):
        with self.lock:
            self.calls += 1
            self.thread_ids.append(get_ident())
        time.sleep(0.05)
        return object()


def test_concurrent_identical_requests_render_once_off_event_loop(
    tmp_path,
    monkeypatch,
):
    raster_path = tmp_path / "singleflight.tif"
    raster_path.write_bytes(b"raster")
    cache = CoordinatedCache()
    engine = SlowEngine()
    caller_thread_id = get_ident()

    monkeypatch.setattr(tile_router.logic, "get_raster_path", _fake_get_raster_path)
    monkeypatch.setattr(tile_router, "tile_cache", cache)
    monkeypatch.setattr(tile_router, "get_tile_engine", lambda path: engine)
    monkeypatch.setattr(tile_router, "_file_version", lambda path: "version-1")
    monkeypatch.setattr(tile_router, "_encode_png", lambda tile: b"rendered-png")

    async def run_requests():
        return await asyncio.gather(
            *[
                tile_router.get_tile(
                    "idx",
                    3,
                    2,
                    3,
                    bands="1,2,3",
                    db={"path": str(raster_path)},
                )
                for _ in range(8)
            ]
        )

    responses = asyncio.run(run_requests())

    assert all(response.status_code == 200 for response in responses)
    assert all(response.body == b"rendered-png" for response in responses)
    assert engine.calls == 1
    assert cache.set_calls == 1
    assert engine.thread_ids[0] != caller_thread_id


def test_tile_response_supports_browser_cache_revalidation(tmp_path, monkeypatch):
    raster_path = tmp_path / "etag.tif"
    raster_path.write_bytes(b"raster")
    monkeypatch.setattr(tile_router.logic, "get_raster_path", _fake_get_raster_path)
    monkeypatch.setattr(tile_router, "tile_cache", FakeCache())
    monkeypatch.setattr(tile_router, "_file_version", lambda path: "version-1")

    first = asyncio.run(
        tile_router.get_tile(
            "idx",
            3,
            2,
            3,
            bands="1",
            db={"path": str(raster_path)},
        )
    )
    second = asyncio.run(
        tile_router.get_tile(
            "idx",
            3,
            2,
            3,
            bands="1",
            if_none_match=first.headers["etag"],
            db={"path": str(raster_path)},
        )
    )

    assert first.status_code == 200
    assert first.headers["cache-control"].startswith("public, max-age=")
    assert first.headers["x-content-type-options"] == "nosniff"
    assert second.status_code == 304
    assert second.body == b""


def test_tile_request_bounds_band_and_xyz_work(monkeypatch):
    monkeypatch.setattr(tile_router.settings, "TILE_MAX_BANDS", 4)
    monkeypatch.setattr(tile_router.settings, "TILE_MAX_ZOOM", 24)

    assert tile_router._parse_bands("1,2,2,3,4,5,999") == [1, 2, 3, 4]

    with pytest.raises(tile_router.HTTPException) as invalid_x:
        tile_router._validate_tile_coordinates(2, 4, 0)
    with pytest.raises(tile_router.HTTPException) as invalid_zoom:
        tile_router._validate_tile_coordinates(25, 0, 0)

    assert invalid_x.value.status_code == 400
    assert invalid_zoom.value.status_code == 400


def test_route_preserves_client_error_for_invalid_xyz(monkeypatch):
    async def unexpected_lookup(db, index_id):
        raise AssertionError("invalid XYZ must be rejected before database lookup")

    monkeypatch.setattr(tile_router.logic, "get_raster_path", unexpected_lookup)

    with pytest.raises(tile_router.HTTPException) as exc_info:
        asyncio.run(
            tile_router.get_tile(
                "idx",
                2,
                4,
                0,
                bands="1",
                db={},
            )
        )

    assert exc_info.value.status_code == 400
