import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from services.ai_gateway import function_registry
from services.ai_gateway.function_registry import (
    AIFunctionInvokeRequest,
    invoke_registered_function,
    list_registered_functions,
)


def _run(awaitable):
    return asyncio.run(awaitable)


def test_vector_tools_are_exposed_to_ai_models_and_agents():
    catalog = list_registered_functions("catalog")
    names = {function["name"] for function in catalog["functions"]}
    categories = {
        function["name"]: function["category"]
        for function in catalog["functions"]
    }

    assert "create_vector_project" in names
    assert "create_vector_feature" in names
    assert "raster_to_vector_layer" in names
    assert "vector_layer_to_raster" in names
    assert categories["create_vector_project"] == "vector_management"
    assert categories["create_vector_feature"] == "vector_features"
    assert categories["raster_to_vector_layer"] == "vector_conversion"


def test_vector_feature_tool_schema_contains_geojson_arguments():
    tools = function_registry.get_registered_openai_tools(["create_vector_feature"])
    parameters = tools[0]["function"]["parameters"]

    assert tools[0]["function"]["name"] == "create_vector_feature"
    assert "layer_id" in parameters["properties"]
    assert "geometry" in parameters["properties"]
    assert "properties" in parameters["properties"]


def test_ai_function_can_create_vector_project(monkeypatch):
    project_id = uuid4()

    class FakeLayerCRUD:
        def __init__(self, db):
            self.db = db

        async def create_project(self, name):
            return SimpleNamespace(
                id=project_id,
                name=name,
                created_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
            )

    monkeypatch.setattr(function_registry, "_get_layer_crud_class", lambda: FakeLayerCRUD)

    result = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="create_vector_project",
                arguments={"name": "AI Vector Project"},
            ),
            db=object(),
            vector_db=object(),
        )
    )

    assert result["status"] == "success"
    assert result["name"] == "create_vector_project"
    assert result["result"]["project"]["id"] == str(project_id)
    assert result["result"]["project"]["name"] == "AI Vector Project"


def test_ai_function_can_create_vector_feature(monkeypatch):
    layer_id = uuid4()
    feature_id = uuid4()
    captured = {}

    class FakeFeatureCRUD:
        def __init__(self, db):
            self.db = db

        async def create(self, target_layer_id, schema):
            captured["layer_id"] = target_layer_id
            captured["schema"] = schema
            return SimpleNamespace(id=feature_id)

        async def get_by_id(self, target_feature_id):
            return {
                "id": target_feature_id,
                "layer_id": layer_id,
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [116.4, 39.9]},
                "properties": {"name": "sample", "category": "poi"},
            }

    monkeypatch.setattr(function_registry, "_get_feature_crud_class", lambda: FakeFeatureCRUD)

    result = _run(
        invoke_registered_function(
            AIFunctionInvokeRequest(
                name="create_vector_feature",
                arguments={
                    "layer_id": str(layer_id),
                    "geometry": {"type": "Point", "coordinates": [116.4, 39.9]},
                    "properties": {"name": "sample"},
                    "category": "poi",
                },
            ),
            db=object(),
            vector_db=object(),
        )
    )

    assert captured["layer_id"] == layer_id
    assert captured["schema"].geometry.type == "Point"
    assert captured["schema"].properties == {"name": "sample"}
    assert result["result"]["feature"]["id"] == str(feature_id)
    assert result["result"]["feature"]["layer_id"] == str(layer_id)
