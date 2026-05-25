import os
import asyncio

from services.tile_service import logic


def test_resolve_raster_path_prefers_existing_cog(tmp_path, monkeypatch):
    raw_path = tmp_path / "raw.tif"
    raw_path.write_text("raw")

    cog_dir = tmp_path / "cog"
    cog_dir.mkdir()
    cog_path = cog_dir / "render.tif"
    cog_path.write_text("cog")

    monkeypatch.setattr(logic, "COG_DIR", str(cog_dir))

    resolved = logic.resolve_raster_path(str(raw_path), "/data/render.tif")

    assert resolved == str(cog_path)


def test_resolve_raster_path_falls_back_to_raw_until_cog_exists(tmp_path, monkeypatch):
    raw_path = tmp_path / "raw.tif"
    raw_path.write_text("raw")

    cog_dir = tmp_path / "cog"
    cog_dir.mkdir()
    monkeypatch.setattr(logic, "COG_DIR", str(cog_dir))

    resolved = logic.resolve_raster_path(str(raw_path), "/data/missing.tif")

    assert resolved == str(raw_path)


def test_resolve_raster_path_accepts_absolute_cog(tmp_path):
    raw_path = tmp_path / "raw.tif"
    raw_path.write_text("raw")
    cog_path = tmp_path / "render.tif"
    cog_path.write_text("cog")

    resolved = logic.resolve_raster_path(str(raw_path), os.fspath(cog_path))

    assert resolved == str(cog_path)


class FakeResult:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class FakeDB:
    def __init__(self, row):
        self.row = row
        self.calls = 0

    async def execute(self, query, params):
        self.calls += 1
        return FakeResult(self.row)


def test_get_raster_path_ttl_cache_hit(tmp_path, monkeypatch):
    raster_path = tmp_path / "cached.tif"
    raster_path.write_text("raster")
    db = FakeDB((str(raster_path), None))
    logic.clear_raster_path_cache()
    monkeypatch.setattr(logic.settings, "TILE_PATH_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(logic.settings, "TILE_PATH_CACHE_MAXSIZE", 1024)

    first = asyncio.run(logic.get_raster_path(db, "idx"))
    second = asyncio.run(logic.get_raster_path(db, "idx"))

    assert first == str(raster_path)
    assert second == str(raster_path)
    assert db.calls == 1


def test_get_raster_path_ttl_cache_expires(tmp_path, monkeypatch):
    raster_path = tmp_path / "expired.tif"
    raster_path.write_text("raster")
    db = FakeDB((str(raster_path), None))
    clock = {"now": 100.0}
    logic.clear_raster_path_cache()
    monkeypatch.setattr(logic.settings, "TILE_PATH_CACHE_TTL_SECONDS", 5.0)
    monkeypatch.setattr(logic.time, "monotonic", lambda: clock["now"])

    first = asyncio.run(logic.get_raster_path(db, "idx-expire"))
    clock["now"] = 106.0
    second = asyncio.run(logic.get_raster_path(db, "idx-expire"))

    assert first == str(raster_path)
    assert second == str(raster_path)
    assert db.calls == 2


def test_get_raster_path_ttl_zero_disables_cache(tmp_path, monkeypatch):
    raster_path = tmp_path / "disabled.tif"
    raster_path.write_text("raster")
    db = FakeDB((str(raster_path), None))
    logic.clear_raster_path_cache()
    monkeypatch.setattr(logic.settings, "TILE_PATH_CACHE_TTL_SECONDS", 0.0)

    first = asyncio.run(logic.get_raster_path(db, "idx-disabled"))
    second = asyncio.run(logic.get_raster_path(db, "idx-disabled"))

    assert first == str(raster_path)
    assert second == str(raster_path)
    assert db.calls == 2
