import json
from types import SimpleNamespace
from uuid import uuid4

import pytest


def _require_worker_deps():
    pytest.importorskip("celery")
    pytest.importorskip("redis")
    pytest.importorskip("rasterio")
    pytest.importorskip("osgeo")


def test_index_tasks_are_registered_and_routed_to_index_queue():
    _require_worker_deps()
    from worker_cluster.app import celery_app

    celery_app.loader.import_default_modules()

    assert "worker_cluster.tasks.index.ndvi" in celery_app.tasks
    route = celery_app.amqp.router.route({}, "worker_cluster.tasks.index.ndvi")
    assert route["queue"].name == "index"


def test_status_payload_is_json_safe_and_clamps_progress(monkeypatch):
    _require_worker_deps()
    from worker_cluster.bridge import status_reporter

    writes = []

    class RedisStub:
        def setex(self, key, ttl, payload):
            writes.append((key, ttl, payload))

    monkeypatch.setattr(status_reporter, "_redis_client", RedisStub())

    task_id = str(uuid4())
    status_reporter.set_task_status(
        task_id,
        "running",
        progress=150,
        result={"generated_id": uuid4()},
    )

    payload = json.loads(writes[0][2])
    assert payload["task_id"] == task_id
    assert payload["progress"] == 100
    assert isinstance(payload["result"]["generated_id"], str)


def test_geojson_export_serializes_geom_column_and_uuid_ids(monkeypatch, tmp_path):
    _require_worker_deps()
    from worker_cluster.tasks.export import geojson

    layer_id = uuid4()
    feature_id = uuid4()
    output_path = tmp_path / "nested" / "layer.geojson"
    executed = {}

    class ResultStub:
        def fetchall(self):
            return [
                SimpleNamespace(
                    id=feature_id,
                    properties={"category": "sample"},
                    geometry='{"type":"Point","coordinates":[120.0,30.0]}',
                )
            ]

    class DbStub:
        def execute(self, sql, params):
            executed["sql"] = str(sql)
            executed["params"] = params
            return ResultStub()

    class DbContext:
        def __enter__(self):
            return DbStub()

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(geojson, "get_sync_db", lambda: DbContext())
    monkeypatch.setattr(geojson.export_geojson_task, "report", lambda progress, message="": None)
    monkeypatch.setattr(
        geojson.export_geojson_task,
        "retry",
        lambda exc, countdown=0: (_ for _ in ()).throw(exc),
    )

    result = geojson.export_geojson_task.run(layer_id, str(output_path))

    assert result == {"output_path": str(output_path), "feature_count": 1}
    assert "ST_AsGeoJSON(f.geom)::json AS geometry" in executed["sql"]
    assert executed["params"] == {"layer_id": layer_id}

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["features"][0]["id"] == str(feature_id)
    assert payload["features"][0]["geometry"]["type"] == "Point"
    assert payload["metadata"]["layer_id"] == str(layer_id)
