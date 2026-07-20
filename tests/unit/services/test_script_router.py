import asyncio
import importlib
from uuid import UUID

import pytest
from fastapi import HTTPException

pytest.importorskip("rasterio")

script_router = importlib.import_module("services.data_service.routers.script_router")


def _run(awaitable):
    return asyncio.run(awaitable)


def test_user_script_passes_selected_feature_geojson_to_executor(monkeypatch):
    feature_id = UUID("76467ec3-bcef-43d5-9428-f66883b6b151")
    layer_id = "9fbc64e1-6123-4701-8cf0-ab18f13690e8"
    feature = {
        "id": str(feature_id),
        "layer_id": layer_id,
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [116.3, 39.9]},
        "properties": {"name": "selected"},
    }
    captured = {}

    async def fake_fetch(requested_id):
        assert requested_id == feature_id
        return feature

    async def fake_dispatch(db, script, raster_ids, output_name, **kwargs):
        captured.update(
            {
                "db": db,
                "script": script,
                "raster_ids": raster_ids,
                "output_name": output_name,
                **kwargs,
            }
        )
        return {"status": "success", "logs": "selected"}

    monkeypatch.setattr(script_router, "internal_fetch_feature", fake_fetch)
    monkeypatch.setattr(script_router, "dispatch_user_script", fake_dispatch)

    result = _run(
        script_router.execute_user_script(
            script="print(feature_0['properties']['name'])",
            raster_ids="",
            feature_ids=str(feature_id),
            output_name="analysis.tif",
            output_required=False,
            db=object(),
        )
    )

    assert result["status"] == "success"
    assert captured["raster_ids"] == []
    assert captured["output_required"] is False
    assert captured["vector_inputs"][0]["feature_id"] == str(feature_id)
    assert captured["vector_inputs"][0]["geojson"] == feature


def test_user_script_rejects_invalid_feature_ids():
    with pytest.raises(HTTPException) as exc_info:
        _run(
            script_router.execute_user_script(
                script="print('x')",
                raster_ids="",
                feature_ids="not-a-uuid",
                output_name="analysis.tif",
                output_required=False,
                db=object(),
            )
        )

    assert exc_info.value.status_code == 400
