import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.data_service.schemas import ClipRasterByVectorRequest

upload_router = importlib.import_module("services.data_service.routers.upload_router")
clip_router = importlib.import_module("services.data_service.routers.clip_router")


@pytest.mark.parametrize("operation", ["merge", "extract", "clip"])
@pytest.mark.parametrize("name", ["../../outside/result", "..\\..\\outside\\result", "/tmp/escape", "C:\\escape", "普通影像"])
def test_untrusted_display_names_cannot_control_output_paths(tmp_path, monkeypatch, operation, name):
    raw = tmp_path / "raw"
    cog = tmp_path / "cog"
    raw.mkdir()
    cog.mkdir()
    source = raw / "input.tif"
    source.write_bytes(b"raster")
    record = SimpleNamespace(file_path=str(source), cog_path=None)
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: record))
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    router = clip_router if operation == "clip" else upload_router
    monkeypatch.setattr(router, "UPLOAD_DIR", str(raw))
    monkeypatch.setattr(router, "COG_DIR", str(cog))
    monkeypatch.setattr(router.db_ops, "_submit_cluster_job_or_none", lambda **kwargs: None)
    captured = {}

    def convert(input_path, output_path):
        resolved = Path(output_path).resolve()
        assert resolved.parent == cog.resolve()
        resolved.write_bytes(b"output")
        captured["output"] = resolved

    async def save(db, task_id, new_name, tmp_path, cog_filename, cog_path, *args, **kwargs):
        assert Path(cog_path).resolve() == captured["output"]
        assert cog_filename == captured["output"].name
        captured["name"] = new_name
        return {"id": 2}

    class Dataset:
        count = 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(router.RasterProcessor, "convert_to_cog", convert)
    monkeypatch.setattr(router.db_ops, "save_to_db", save)
    monkeypatch.setattr(upload_router.rasterio, "open", lambda *args: Dataset())
    if operation == "clip":
        monkeypatch.setattr(router.RasterProcessor, "clip_raster_by_vector", lambda **kwargs: {"bands": 1})
        payload = ClipRasterByVectorRequest(raster_id=1, new_name=name, geometries=[{"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}])
        asyncio.run(router.clip_raster_by_vector(payload, db))
        assert captured["name"] == f"{name}.tif"
    else:
        monkeypatch.setattr(router.RasterProcessor, "merge_bands", lambda *args: None)
        monkeypatch.setattr(router.RasterProcessor, "extract_bands", lambda *args: None)
        operation_call = router.merge_raster_bands_task("1", name, db) if operation == "merge" else router.extract_raster_bands_task(1, "1", name, db)
        asyncio.run(operation_call)
        assert captured["name"] == name
