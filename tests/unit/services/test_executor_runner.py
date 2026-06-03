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
    def __init__(self):
        self.run_kwargs = None

    def run(self, **kwargs):
        self.run_kwargs = kwargs
        output_dir = next(
            host_path
            for host_path, spec in kwargs["volumes"].items()
            if spec["bind"] == runner.CONTAINER_OUTPUT_DIR
        )
        output_name = kwargs["environment"]["OUTPUT_FILENAME"]
        Path(output_dir, output_name).write_bytes(b"fake-tif")
        return _FakeContainer()


class _FakeDockerClient:
    def __init__(self):
        self.images = _FakeImages()
        self.containers = _FakeContainers()


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
