import asyncio
import logging

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
        tile_router.get_tile("idx", 1, 2, 3, bands="1", db={"path": str(raster_path)})
    )

    assert response.status_code == 200
    assert "tile_route_profile" not in caplog.text

    caplog.clear()
    monkeypatch.setenv("TILE_PROFILE", "1")
    response = asyncio.run(
        tile_router.get_tile("idx", 1, 2, 3, bands="1", db={"path": str(raster_path)})
    )

    assert response.status_code == 200
    assert "tile_route_profile" in caplog.text
    assert "path=profile.tif" in caplog.text
