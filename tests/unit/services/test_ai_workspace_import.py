import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from services.ai_gateway import artifacts
from services.ai_gateway import workspace_import as workspace
from services.ai_gateway.agent_security import authorize_tool_call, DelegatedTaskGrant
from services.ai_gateway.function_registry import AIFunctionInvokeRequest, invoke_registered_function


@pytest.fixture(autouse=True)
def artifact_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(artifacts, "BASE_DIR", tmp_path)


def document():
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[121, 31], [121.1, 31.2]]},
         "properties": {"label": "shore", "score": 0.8, "verified": False, "category": "coastline"}},
    ]}


def generated(data=None):
    return artifacts.create_document_artifact("coastline.json", json.dumps(data or document()), "json")


class VectorDB:
    def __init__(self):
        self.added = []
        self.rows = []
        self.existing = None
        self.fail = False
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.flush = AsyncMock()

    def add(self, row):
        self.added.append(row)

    async def get(self, model, identifier):
        return self.existing if model.__name__ == "Layer" else None

    async def scalar(self, query):
        return len(self.rows)

    async def execute(self, statement, rows=None):
        if rows:
            if self.fail:
                raise RuntimeError("insert failed")
            self.rows.extend(rows)


def test_generated_json_import_registers_layer_fields_and_exact_geometry():
    from geoalchemy2.shape import to_shape
    db = VectorDB()
    artifact = generated()
    result = asyncio.run(invoke_registered_function(AIFunctionInvokeRequest(
        name="import_generated_artifact", arguments={"artifact_id": artifact["artifact_id"], "name": "Coastline"}
    ), None, db))["result"]
    assert result["workspace_import"]["data_type"] == "vector"
    assert result["workspace_import"]["feature_count"] == 1
    assert [list(point) for point in to_shape(db.rows[0]["geom"]).coords] == document()["features"][0]["geometry"]["coordinates"]
    assert db.rows[0]["properties"] == document()["features"][0]["properties"]
    assert {row.field_name: row.field_type for row in db.added if hasattr(row, "field_name")} == {
        "label": "string", "score": "number", "verified": "boolean", "category": "string"}
    assert db.rows[0]["category"] == "coastline"
    db.commit.assert_awaited_once()
    assert artifacts.get_artifact(artifact["artifact_id"])[1].is_file()


def test_reimport_is_idempotent_and_does_not_overwrite():
    db = VectorDB()
    artifact = generated()
    args = workspace.WorkspaceImportArgs(artifact_id=artifact["artifact_id"], name="First name")
    first = asyncio.run(workspace.import_generated_artifact(args, None, db))
    db.existing = SimpleNamespace(name="First name")
    second = asyncio.run(workspace.import_generated_artifact(args.model_copy(update={"name": "Do not rename"}), None, db))
    assert second["workspace_import"]["reused"] is True
    assert second["workspace_import"]["name"] == "First name"
    assert first["workspace_import"]["layer_id"] == second["workspace_import"]["layer_id"]
    assert len(db.rows) == 1


def test_insert_failure_rolls_back_project_layer_and_features():
    db = VectorDB()
    db.fail = True
    artifact = generated()
    with pytest.raises(RuntimeError, match="insert failed"):
        asyncio.run(workspace.import_generated_artifact(workspace.WorkspaceImportArgs(artifact_id=artifact["artifact_id"], name="Test"), None, db))
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("data", [
    {"type": "FeatureCollection", "features": []},
    {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None}]},
    {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [1000, 91]}}]},
    {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,1],[1,0],[0,1],[0,0]]]}}]},
    {"type": "not-geojson"},
])
def test_invalid_geometry_never_writes_to_database(data):
    db = VectorDB()
    artifact = generated(data)
    with pytest.raises(ValueError):
        asyncio.run(workspace.import_generated_artifact(workspace.WorkspaceImportArgs(artifact_id=artifact["artifact_id"], name="Invalid"), None, db))
    assert db.rows == [] and db.added == []
    db.commit.assert_not_awaited()


def test_missing_project_rolls_back_without_creating_a_different_project():
    db = VectorDB()
    artifact = generated()
    with pytest.raises(ValueError, match="project does not exist"):
        asyncio.run(workspace.import_generated_artifact(workspace.WorkspaceImportArgs(
            artifact_id=artifact["artifact_id"], name="Test", project_id=uuid4()), None, db))
    assert not db.added
    db.rollback.assert_awaited_once()


def test_import_respects_permission_tier_and_derived_assignment():
    args = {"artifact_id": "a" * 32, "name": "Coastline"}
    task = "帮我提取海岸线的矢量数据"
    assert authorize_tool_call("import_generated_artifact", args, task).allowed
    assert not authorize_tool_call("import_generated_artifact", args, task, permission_level="read_only").allowed
    assert not authorize_tool_call("import_generated_artifact", args, "不要创建任何输出").allowed
    assignment = DelegatedTaskGrant(task_id="save", instruction="Import the validated coastline as a new workspace layer", tool_names=frozenset({"import_generated_artifact"}), write_targets=frozenset())
    assert authorize_tool_call("import_generated_artifact", args, task, delegation=assignment).allowed


def test_paths_and_nonspatial_documents_are_rejected():
    with pytest.raises(ValueError):
        workspace.WorkspaceImportArgs(artifact_id="../source", name="Unsafe")
    with pytest.raises(ValueError):
        workspace.WorkspaceImportArgs(artifact_id="a" * 32, name="Unsafe", path="/etc/passwd")
    artifact = artifacts.create_document_artifact("report.md", "Report", "md")
    with pytest.raises(ValueError, match="GeoJSON or georeferenced GeoTIFF"):
        asyncio.run(workspace.import_generated_artifact(workspace.WorkspaceImportArgs(artifact_id=artifact["artifact_id"], name="Report"), None, VectorDB()))


@pytest.mark.parametrize("constraint", ["只要下载", "不要导入工作区", "download only", "do not import"])
def test_download_only_constraints_survive_continuation_and_delegation(constraint):
    from services.ai_gateway.agent_security import extract_task_constraints

    retained = extract_task_constraints(constraint)
    assert retained == [constraint]
    assignment = DelegatedTaskGrant(task_id="save", instruction="Import the output", tool_names=frozenset({"import_generated_artifact"}), write_targets=frozenset())
    decision = authorize_tool_call("import_generated_artifact", {"artifact_id": "a" * 32, "name": "Coastline"},
                                   "继续", task_scope="帮我提取海岸线", constraints=tuple(retained), delegation=assignment)
    assert not decision.allowed


def test_agent_response_exposes_only_successful_workspace_imports():
    from services.ai_gateway.agent_handler import AgentRequestPayload, AgentStep, _agent_response

    result = {"data_type": "vector", "project_id": str(uuid4()), "layer_id": str(uuid4())}
    steps = [AgentStep(step=1, type="tool", tool_call_id="import", name="import_generated_artifact", arguments={}, status="success", result={"result": {"workspace_import": result}})]
    response = _agent_response(payload=AgentRequestPayload(user_prompt="Import the coastline"), session_id="import-response-test", status="success", answer="Imported", steps=steps)
    assert response["workspace_imports"] == [result]
    steps[0].status = "error"
    response = _agent_response(payload=AgentRequestPayload(user_prompt="Import the coastline"), session_id="import-response-test", status="interrupted", answer="Failed", steps=steps)
    assert response["workspace_imports"] == []


def test_raster_import_preserves_original_bytes_across_conversion_and_retry(monkeypatch, tmp_path):
    import numpy as np
    import rasterio
    import shutil
    from rasterio.transform import from_origin
    from services.data_service.processor import RasterProcessor

    source = tmp_path / "source.tif"
    with rasterio.open(source, "w", driver="GTiff", width=2, height=2, count=1, dtype="uint8", crs="EPSG:4326", transform=from_origin(121, 31, .01, .01)) as output:
        output.write(np.ones((1, 2, 2), dtype="uint8"))
    original = source.read_bytes()

    def convert(input_path, output_path):
        # The production converter may add internal overviews to its input.
        from pathlib import Path
        source_path = Path(input_path)
        source_path.write_bytes(source_path.read_bytes() + b"overview")
        shutil.copyfile(input_path, output_path)

    monkeypatch.setattr(RasterProcessor, "convert_to_cog", convert)
    raw, cog, bands = workspace._prepare_raster(source, "a" * 32)
    assert bands == 1 and cog.is_file()
    assert raw.read_bytes() == original == source.read_bytes()
    assert workspace._prepare_raster(source, "a" * 32) == (raw, cog, bands)


def test_plain_tiff_cannot_be_registered_without_spatial_metadata(tmp_path):
    from PIL import Image

    source = tmp_path / "plain.tif"
    Image.new("RGB", (2, 2)).save(source)
    with pytest.raises(ValueError, match="CRS and georeferencing"):
        workspace._prepare_raster(source, "a" * 32)
    assert not (tmp_path / "storage/raw").exists()
