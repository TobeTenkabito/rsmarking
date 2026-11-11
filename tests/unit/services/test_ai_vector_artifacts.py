import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.ai_gateway import artifacts, function_registry
from services.ai_gateway.agent_security import authorize_tool_call
from services.ai_gateway.router import router
from services.ai_gateway.vector_artifacts import create_geojson_artifact, inspect_geojson_artifact


def collection():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"threshold": 0.1},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[121.8, 31.15], [121.81, 31.16]],
                },
            }
        ],
    }


def test_saved_coordinates_download_and_independent_inspection(monkeypatch, tmp_path):
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path)
    artifact = create_geojson_artifact("coastline.tif", collection())
    assert artifact["name"] == "coastline.geojson"
    inspection = inspect_geojson_artifact(artifact["artifact_id"], [121.78, 31.12, 121.88, 31.22])
    assert inspection["geometry_types"] == {"LineString": 1}
    assert inspection["feature_count"] == 1
    assert (
        inspection["invalid_count"]
        == inspection["empty_count"]
        == inspection["outside_expected_bbox"]
        == 0
    )
    assert 1000 < inspection["line_length_m"] < 2000
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        result = client.get(artifact["download_url"])
        assert result.json() == collection()
        assert "application/geo+json" in result.headers["content-type"]
    _, path = artifacts.get_artifact(artifact["artifact_id"])
    path.write_text('{"type":"FeatureCollection","features":[]}')
    reread = inspect_geojson_artifact(artifact["artifact_id"])
    assert reread["feature_count"] == 0
    assert reread["sha256"] != inspection["sha256"]


def test_inspection_detects_outside_extent_and_rejects_projected_coordinates(monkeypatch, tmp_path):
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path)
    artifact = create_geojson_artifact("coast", collection())
    assert (
        inspect_geojson_artifact(artifact["artifact_id"], [120, 30, 121, 31])[
            "outside_expected_bbox"
        ]
        == 1
    )
    document = collection()
    document["features"][0]["geometry"]["coordinates"][0] = [400000, 3400000]
    with pytest.raises(ValueError, match="WGS84"):
        create_geojson_artifact("projected", document)
    with pytest.raises(artifacts.ArtifactNotFoundError):
        inspect_geojson_artifact("../secrets")
    assert authorize_tool_call(
        "inspect_geojson_artifact",
        {"artifact_id": artifact["artifact_id"]},
        "检查成果",
        permission_level="read_only",
    ).allowed


def test_sandbox_geometry_reaches_artifact_without_model_coordinate_roundtrip(
    monkeypatch, tmp_path
):
    from services.data_service.bridges import executor_bridge

    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path)

    async def dispatch(**kwargs):
        assert kwargs["output_format"] == "geojson"
        assert kwargs["output_required"] is True
        return {"status": "success", "geojson": collection(), "logs": "created 1 coastline"}

    monkeypatch.setattr(executor_bridge, "dispatch_user_script", dispatch)
    args = function_registry.ScriptSandboxArgs(
        script="print('test coastline')",
        output_name="coastline",
        output_format="geojson",
        require_raster_output=False,
    )
    result = asyncio.run(function_registry._run_script_sandbox(args, object(), object()))
    assert "geojson" not in result
    assert "coordinates" not in json.dumps(result)
    assert inspect_geojson_artifact(result["artifact"]["artifact_id"])["feature_count"] == 1


def test_boundary_sampling_checks_real_pixels_and_ignores_nodata(monkeypatch, tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from pyproj import Transformer
    from services.ai_gateway.vector_artifacts import inspect_raster_boundary

    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path / "artifacts")
    raster_path = tmp_path / "water.tif"
    data = np.full((100, 100), -0.2, dtype="float32")
    data[:, 50:] = 0.3
    data[:20] = -9999
    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        width=100,
        height=100,
        count=1,
        dtype="float32",
        crs="EPSG:32651",
        transform=from_origin(400000, 3450000, 30, 30),
        nodata=-9999,
    ) as raster:
        raster.write(data, 1)
    transform = Transformer.from_crs(32651, 4326, always_xy=True)
    document = collection()
    document["features"][0]["geometry"]["coordinates"] = [
        transform.transform(401500, 3449970),
        transform.transform(401500, 3447030),
    ]
    artifact = create_geojson_artifact("boundary", document)
    check = inspect_raster_boundary(artifact["artifact_id"], str(raster_path), 0)
    assert check["sample_count"] == 200
    assert 100 < check["valid_pair_count"] < 200
    assert check["opposite_class_fraction"] == 1
    wrong = inspect_raster_boundary(artifact["artifact_id"], str(raster_path), 0.9)
    assert wrong["opposite_class_fraction"] == 0
