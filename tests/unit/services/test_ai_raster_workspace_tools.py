import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from services.ai_gateway import function_registry
from services.ai_gateway.function_registry import (
    AIFunctionInvokeRequest,
    invoke_registered_function,
    list_registered_functions,
)


def _run(awaitable):
    return asyncio.run(awaitable)


def _raster(index_id=101, record_id=7):
    return SimpleNamespace(
        id=record_id,
        index_id=index_id,
        file_name="source.tif",
        bundle_id="bundle-1",
        crs="EPSG:4326",
        bounds=[0, 0, 1, 1],
        bounds_wgs84=[0, 0, 1, 1],
        center=[0.5, 0.5],
        width=64,
        height=32,
        bands=3,
        data_type="uint16",
        resolution_x=0.1,
        resolution_y=0.1,
        created_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )


def test_raster_workspace_tools_are_exposed_to_ai_models():
    catalog = list_registered_functions("catalog")
    functions = {item["name"]: item for item in catalog["functions"]}

    expected = {
        "list_rasters",
        "get_raster_metadata",
        "get_raster_statistics",
        "query_raster_spectrum",
        "delete_raster",
        "list_raster_fields",
        "create_raster_field",
        "update_raster_field",
        "delete_raster_field",
        "get_processing_task_status",
        "get_processing_job_status",
        "list_script_templates",
    }

    assert expected.issubset(functions)
    assert functions["list_rasters"]["category"] == "raster_catalog"
    assert functions["create_raster_field"]["category"] == "raster_fields"
    assert functions["get_processing_task_status"]["category"] == "task_monitoring"
    stats_schema = functions["get_raster_statistics"]["parameters"]["properties"]
    assert {"raster_id", "bins", "max_size", "band_indices"}.issubset(stats_schema)


def test_raster_catalog_tools_list_get_and_delete_by_index_id(monkeypatch):
    records = [_raster(), _raster(index_id=202, record_id=8)]
    deleted_record_ids = []

    class FakeRasterCRUD:
        @staticmethod
        async def get_all_rasters(db):
            return records

        @staticmethod
        async def get_raster_by_index_id(db, raster_id):
            return next((item for item in records if item.index_id == raster_id), None)

        @staticmethod
        async def delete_raster(db, record_id):
            deleted_record_ids.append(record_id)
            return True

    monkeypatch.setattr(function_registry, "_get_raster_crud_class", lambda: FakeRasterCRUD)

    listed = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(name="list_rasters", arguments={"limit": 1}),
            db=object(),
            vector_db=object(),
        )
    )
    loaded = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(name="get_raster_metadata", arguments={"raster_id": 101}),
            db=object(),
            vector_db=object(),
        )
    )
    deleted = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(name="delete_raster", arguments={"raster_id": 101}),
            db=object(),
            vector_db=object(),
        )
    )

    assert listed["result"]["count"] == 1
    assert listed["result"]["total"] == 2
    assert listed["result"]["truncated"] is True
    assert "file_path" not in listed["result"]["rasters"][0]
    assert loaded["result"]["raster"]["index_id"] == 101
    assert deleted["result"]["deleted"] is True
    assert deleted_record_ids == [7]


def test_raster_inspection_tools_use_registered_record_path(monkeypatch):
    record = _raster()
    captured = {}

    class FakeRasterCRUD:
        @staticmethod
        async def get_raster_by_index_id(db, raster_id):
            return record if raster_id == record.index_id else None

    class FakeOps:
        @staticmethod
        def resolve_raster_record_path(candidate):
            assert candidate is record
            return "resolved-source.tif"

    class FakeProcessor:
        @staticmethod
        def query_spectrum(path, lng, lat):
            captured["spectrum"] = (path, lng, lat)
            return {"bands": [{"index": 1, "value": 0.42}]}

    def fake_statistics(path, **kwargs):
        captured["statistics"] = (path, kwargs)
        return {"band_count": 3, "bands": []}

    monkeypatch.setattr(function_registry, "_get_raster_crud_class", lambda: FakeRasterCRUD)
    monkeypatch.setattr(function_registry, "_get_data_service_ops", lambda: FakeOps)
    monkeypatch.setattr(function_registry, "_get_raster_processor", lambda: FakeProcessor)
    monkeypatch.setattr(function_registry, "_get_compute_raster_statistics", lambda: fake_statistics)

    stats = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="get_raster_statistics",
                arguments={"raster_id": 101, "bins": 16, "band_indices": [1, 3]},
            ),
            db=object(),
            vector_db=object(),
        )
    )
    spectrum = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="query_raster_spectrum",
                arguments={"raster_id": 101, "lng": 116.4, "lat": 39.9},
            ),
            db=object(),
            vector_db=object(),
        )
    )

    assert captured["statistics"][0] == "resolved-source.tif"
    assert captured["statistics"][1]["band_indices"] == [1, 3]
    assert stats["result"]["statistics"]["band_count"] == 3
    assert captured["spectrum"] == ("resolved-source.tif", 116.4, 39.9)
    assert spectrum["result"]["spectrum"]["bands"][0]["value"] == 0.42


def test_raster_field_and_status_tools_are_directly_invokable(monkeypatch):
    record = _raster()
    field = SimpleNamespace(
        id=5,
        raster_index_id=101,
        field_name="quality",
        field_alias="Quality",
        field_type="string",
        field_order=0,
        is_required=False,
        is_system=False,
        default_val="good",
        created_at=None,
    )

    class FakeRasterCRUD:
        @staticmethod
        async def get_raster_by_index_id(db, raster_id):
            return record if raster_id == 101 else None

    class FakeFieldCRUD:
        def __init__(self, db):
            self.db = db

        async def get_by_raster(self, raster_id):
            return [field]

        async def get_by_id(self, field_id):
            return field if field_id == 5 else None

        async def create(self, raster_id, payload):
            assert payload.field_name == "quality"
            return field

        async def update(self, field_id, payload):
            field.field_alias = payload.field_alias
            return field

        async def delete(self, field_id):
            return field_id == 5

    async def fake_templates():
        return [{"name": "Example", "description": "Example script", "code": "print('ok')"}]

    monkeypatch.setattr(function_registry, "_get_raster_crud_class", lambda: FakeRasterCRUD)
    monkeypatch.setattr(function_registry, "_get_raster_field_crud_class", lambda: FakeFieldCRUD)
    monkeypatch.setattr(
        function_registry,
        "_get_cluster_task_status",
        lambda task_id: {"task_id": task_id, "status": "running", "progress": 50},
    )
    monkeypatch.setattr(function_registry, "_get_script_templates_func", lambda: fake_templates)

    listed = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(name="list_raster_fields", arguments={"raster_id": 101}),
            db=object(),
            vector_db=object(),
        )
    )
    created = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="create_raster_field",
                arguments={"raster_id": 101, "field_name": "quality"},
            ),
            db=object(),
            vector_db=object(),
        )
    )
    updated = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="update_raster_field",
                arguments={"raster_id": 101, "field_id": 5, "field_alias": "QA"},
            ),
            db=object(),
            vector_db=object(),
        )
    )
    task = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="get_processing_task_status",
                arguments={"task_id": "task-1"},
            ),
            db=object(),
            vector_db=object(),
        )
    )
    templates = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(name="list_script_templates", arguments={}),
            db=object(),
            vector_db=object(),
        )
    )
    deleted = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="delete_raster_field",
                arguments={"raster_id": 101, "field_id": 5},
            ),
            db=object(),
            vector_db=object(),
        )
    )

    assert listed["result"]["count"] == 1
    assert created["result"]["field"]["field_name"] == "quality"
    assert updated["result"]["field"]["field_alias"] == "QA"
    assert task["result"]["task"]["progress"] == 50
    assert templates["result"]["templates"] == [
        {"name": "Example", "description": "Example script"}
    ]
    assert deleted["result"]["deleted"] is True


def test_processing_job_status_is_read_from_job_store(monkeypatch):
    class FakeMappings:
        def first(self):
            return {
                "job_id": "job-1",
                "celery_task_id": "task-1",
                "task_type": "dem_analysis",
                "status": "running",
                "created_at": datetime(2026, 6, 23, tzinfo=timezone.utc),
            }

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeDB:
        async def execute(self, statement, parameters):
            assert parameters == {"job_id": "job-1"}
            return FakeResult()

    monkeypatch.setattr(
        function_registry,
        "_get_cluster_task_status",
        lambda task_id: {"task_id": task_id, "status": "running"},
    )

    result = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="get_processing_job_status",
                arguments={"job_id": "job-1"},
            ),
            db=FakeDB(),
            vector_db=object(),
        )
    )

    assert result["result"]["job"]["status"] == "running"
    assert result["result"]["job"]["created_at"] == "2026-06-23T00:00:00+00:00"
    assert result["result"]["job"]["task_status"]["task_id"] == "task-1"
