import json
from pathlib import Path

import pytest

pytest.importorskip("docker")

from services.executor_service import runner


class _FakeImage:
    @property
    def attrs(self):
        return {
            "Config": {
                "Labels": {
                    runner.SANDBOX_SPEC_HASH_LABEL: runner._image_context_hash(),
                },
            },
        }


class _FakeImages:
    def get(self, image_name):
        return _FakeImage()

    def build(self, **kwargs):
        return (_FakeImage(), [])


class _FakeContainer:
    def wait(self, timeout=None, condition=None):
        return {"StatusCode": 0}

    def logs(self, stdout=True, stderr=True):
        return b"fake sandbox log"

    def remove(self, force=False):
        return None


class _FakeContainers:
    def __init__(self, create_output=True):
        self.run_kwargs = None
        self.create_output = create_output

    def run(self, **kwargs):
        self.run_kwargs = kwargs
        if self.create_output:
            output_dir = next(
                host_path
                for host_path, spec in kwargs["volumes"].items()
                if spec["bind"] == runner.CONTAINER_OUTPUT_DIR
            )
            output_name = kwargs["environment"]["OUTPUT_FILENAME"]
            Path(output_dir, output_name).write_bytes(b"fake-tif")
        return _FakeContainer()


class _FakeDockerClient:
    def __init__(self, create_output=True):
        self.images = _FakeImages()
        self.containers = _FakeContainers(create_output=create_output)


def test_run_in_sandbox_moves_isolated_output_to_raw_storage(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    tmp_dir = tmp_path / "tmp"
    input_dir = tmp_path / "inputs"
    raw_dir.mkdir()
    tmp_dir.mkdir()
    input_dir.mkdir()
    input_file = input_dir / "source.tif"
    input_file.write_bytes(b"source")

    fake_client = _FakeDockerClient()
    monkeypatch.setattr(runner, "client", fake_client)
    monkeypatch.setattr(runner, "HOST_RAW_DIR", str(raw_dir))
    monkeypatch.setattr(runner, "HOST_TMP_DIR", str(tmp_dir))
    monkeypatch.setattr(runner, "SANDBOX_ALLOWED_INPUT_ROOTS", (str(tmp_path),))

    result = runner.run_in_sandbox(
        script_content="print('ok')",
        input_filenames=[],
        output_filename="result.tif",
        script_id="task-1",
        input_files=[{"path": str(input_file), "name": "source.tif"}],
    )

    assert result["status"] == "success"
    assert Path(result["output_path"]) == raw_dir / "result.tif"
    assert (raw_dir / "result.tif").read_bytes() == b"fake-tif"
    assert not list(tmp_dir.glob("output_task-1*"))
    assert fake_client.containers.run_kwargs["read_only"] is True
    assert fake_client.containers.run_kwargs["network_disabled"] is True


def test_run_in_sandbox_preserves_duplicate_rasters_and_vector_metadata(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    tmp_dir = tmp_path / "tmp"
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    for directory in (raw_dir, tmp_dir, first_dir, second_dir):
        directory.mkdir()
    first_input = first_dir / "source.tif"
    second_input = second_dir / "source.tif"
    first_input.write_bytes(b"first")
    second_input.write_bytes(b"second")

    fake_client = _FakeDockerClient()
    monkeypatch.setattr(runner, "client", fake_client)
    monkeypatch.setattr(runner, "HOST_RAW_DIR", str(raw_dir))
    monkeypatch.setattr(runner, "HOST_TMP_DIR", str(tmp_dir))
    monkeypatch.setattr(runner, "SANDBOX_ALLOWED_INPUT_ROOTS", (str(tmp_path),))

    result = runner.run_in_sandbox(
        script_content="print(feature_0, input_0, input_1)",
        input_filenames=[],
        output_filename="result.tif",
        script_id="../../unsafe/task",
        input_files=[
            {"path": str(first_input), "name": "source.tif", "raster_id": 1},
            {"path": str(second_input), "name": "source.tif", "raster_id": 2},
        ],
        vector_inputs=[
            {
                "name": "selected.geojson",
                "alias": "selected_feature",
                "feature_id": "feature-1",
                "layer_id": "layer-1",
                "geojson": {
                    "id": "feature-1",
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 2]},
                    "properties": {},
                },
            }
        ],
    )

    assert result["status"] == "success"
    assert result["input_files"] == ["source.tif", "source_2.tif"]
    raster_map = json.loads(
        fake_client.containers.run_kwargs["environment"]["SANDBOX_INPUT_MAP"]
    )
    vector_map = json.loads(
        fake_client.containers.run_kwargs["environment"]["SANDBOX_VECTOR_MAP"]
    )
    assert [item["name"] for item in raster_map] == ["source.tif", "source_2.tif"]
    assert vector_map[0]["feature_id"] == "feature-1"
    script_mount = next(
        Path(host_path)
        for host_path, spec in fake_client.containers.run_kwargs["volumes"].items()
        if spec["bind"] == f"{runner.CONTAINER_SCRIPT_DIR}/user_code.py"
    )
    assert script_mount.parent == tmp_dir


def test_run_in_sandbox_can_return_logs_without_an_output(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    tmp_dir = tmp_path / "tmp"
    raw_dir.mkdir()
    tmp_dir.mkdir()

    fake_client = _FakeDockerClient(create_output=False)
    monkeypatch.setattr(runner, "client", fake_client)
    monkeypatch.setattr(runner, "HOST_RAW_DIR", str(raw_dir))
    monkeypatch.setattr(runner, "HOST_TMP_DIR", str(tmp_dir))

    result = runner.run_in_sandbox(
        script_content="print('analysis complete')",
        input_filenames=[],
        output_filename="unused.tif",
        script_id="analysis",
        input_files=[],
        output_required=False,
    )

    assert result["status"] == "success"
    assert result["output_path"] is None
    assert result["logs"] == "fake sandbox log"


def test_validated_input_path_rejects_files_outside_storage_roots(tmp_path, monkeypatch):
    allowed_dir = tmp_path / "allowed"
    outside_dir = tmp_path / "outside"
    allowed_dir.mkdir()
    outside_dir.mkdir()
    allowed_file = allowed_dir / "allowed.tif"
    outside_file = outside_dir / "outside.tif"
    allowed_file.write_bytes(b"allowed")
    outside_file.write_bytes(b"outside")
    monkeypatch.setattr(runner, "SANDBOX_ALLOWED_INPUT_ROOTS", (str(allowed_dir),))

    assert runner._validated_input_path(str(allowed_file)) == str(allowed_file)
    with pytest.raises(ValueError, match="outside the configured"):
        runner._validated_input_path(str(outside_file))
