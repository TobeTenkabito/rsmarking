import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

pytest.importorskip("fastapi")
from services.data_service.bridges import vector_bridge


pytestmark = pytest.mark.integration


def _run(awaitable):
    return asyncio.run(awaitable)


def _record_httpx_requests(monkeypatch, module, responses):
    requests = []
    real_async_client = httpx.AsyncClient
    pending_responses = iter(responses)

    def handler(request):
        requests.append(request)
        status_code, payload = next(pending_responses)
        return httpx.Response(status_code, json=payload, request=request)

    transport = httpx.MockTransport(handler)

    def build_client(*args, **kwargs):
        return real_async_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", build_client)
    return requests


def _request_json(request):
    return json.loads(request.content.decode())


def test_layer_bridge_posts_to_annotation_service_port(monkeypatch):
    project_id = uuid4()
    expected_layer = {"id": "layer-17", "name": "Polygonized water"}
    requests = _record_httpx_requests(monkeypatch, vector_bridge, [(201, expected_layer)])

    result = _run(
        vector_bridge.internal_create_layer(
            project_id,
            "Polygonized water",
            source_raster_index_id=1729,
        )
    )

    assert result == expected_layer
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.port == 8001
    assert requests[0].url.path == f"/projects/{project_id}/layers"
    assert _request_json(requests[0]) == {
        "name": "Polygonized water",
        "source_raster_index_id": 1729,
    }


def test_export_bridge_reads_features_and_fields_from_annotation_port(monkeypatch):
    layer_id = uuid4()
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [120.0, 30.0]},
        "properties": {"category": "sample"},
    }
    field = {"field_name": "category", "field_type": "string"}
    requests = _record_httpx_requests(
        monkeypatch,
        vector_bridge,
        [
            (200, {"type": "FeatureCollection", "features": [feature]}),
            (200, [field]),
        ],
    )

    features = _run(vector_bridge.internal_fetch_features(layer_id))
    fields = _run(vector_bridge.internal_fetch_fields(layer_id))

    assert features == [feature]
    assert fields == [field]
    assert [(request.method, request.url.port, request.url.path) for request in requests] == [
        ("GET", 8001, f"/layers/{layer_id}/features/export"),
        ("GET", 8001, f"/{layer_id}/fields"),
    ]


def test_script_bridge_posts_to_executor_service_port(monkeypatch, tmp_path):
    pytest.importorskip("osgeo")
    pytest.importorskip("rasterio")

    from services.data_service.bridges import executor_bridge

    input_path = tmp_path / "source.tif"
    input_path.write_bytes(b"source")
    output_path = tmp_path / "executor-output.tif"
    output_path.write_bytes(b"output")
    raster = SimpleNamespace(
        index_id=42,
        file_path=str(input_path),
        cog_path=None,
    )

    async def fake_get_raster_by_index_id(db, raster_id):
        assert raster_id == 42
        return raster

    async def fake_save_to_db(**kwargs):
        assert kwargs["new_name"] == "Script result"
        return {"id": 19, "cog_url": "/data/script-result.tif"}

    class RasterSource:
        count = 1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        executor_bridge.RasterCRUD,
        "get_raster_by_index_id",
        fake_get_raster_by_index_id,
    )
    monkeypatch.setattr(executor_bridge.RasterProcessor, "convert_to_cog", lambda *args: None)
    monkeypatch.setattr(executor_bridge.rasterio, "open", lambda path: RasterSource())
    monkeypatch.setattr(executor_bridge, "save_to_db", fake_save_to_db)
    monkeypatch.setattr(executor_bridge, "EXECUTOR_URL", "http://localhost:8004/execute")
    requests = _record_httpx_requests(
        monkeypatch,
        executor_bridge,
        [
            (
                200,
                {
                    "status": "success",
                    "output_path": str(output_path),
                    "logs": "sandbox complete",
                },
            )
        ],
    )

    result = _run(
        executor_bridge.dispatch_user_script(
            object(),
            "print('script ready')",
            [42],
            "Script result",
        )
    )

    assert result == {
        "status": "success",
        "id": 19,
        "cog_url": "/data/script-result.tif",
        "logs": "sandbox complete",
    }
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.port == 8004
    assert requests[0].url.path == "/execute"
    payload = _request_json(requests[0])
    assert payload["script"] == "print('script ready')"
    assert payload["input_files"] == [
        {"path": str(input_path), "name": "source.tif", "raster_id": 42, "alias": "raster_42"}
    ]
    assert payload["output_name"].endswith("_script_raw.tif")
