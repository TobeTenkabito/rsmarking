import os

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
