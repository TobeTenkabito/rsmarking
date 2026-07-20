import json
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from services.executor_service.runtime import sandbox_entry


def test_runtime_injects_real_geojson_features_into_user_code(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    script_dir = tmp_path / "scripts"
    input_dir.mkdir()
    output_dir.mkdir()
    script_dir.mkdir()

    feature_id = "76467ec3-bcef-43d5-9428-f66883b6b151"
    layer_id = "9fbc64e1-6123-4701-8cf0-ab18f13690e8"
    vector_name = f"feature_{feature_id}.geojson"
    feature = {
        "id": feature_id,
        "layer_id": layer_id,
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        },
        "properties": {"name": "actual selected feature"},
    }
    (input_dir / vector_name).write_text(
        json.dumps(feature),
        encoding="utf-8",
    )

    script_path = script_dir / "user_code.py"
    script_path.write_text(
        "\n".join(
            [
                f"assert feature_0['id'] == '{feature_id}'",
                f"assert feature_by_id['{feature_id}']['properties']['name'] == 'actual selected feature'",
                "assert feature_geometry(0)['type'] == 'Polygon'",
                "assert round(feature_shape(0).area, 6) == 1.0",
                "profile = {",
                "    'driver': 'GTiff',",
                "    'height': 2,",
                "    'width': 2,",
                "    'count': 1,",
                "    'dtype': 'uint8',",
                "    'crs': 'EPSG:4326',",
                "    'transform': rasterio.transform.from_origin(0, 2, 1, 1),",
                "}",
                "write_raster(np.full((2, 2), 7, dtype=np.uint8), profile)",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sandbox_entry, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(sandbox_entry, "OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(sandbox_entry, "SCRIPT_PATH", str(script_path))
    monkeypatch.setenv("OUTPUT_FILENAME", "result.tif")
    monkeypatch.setenv("SANDBOX_INPUT_MAP", "[]")
    monkeypatch.setenv(
        "SANDBOX_VECTOR_MAP",
        json.dumps(
            [
                {
                    "index": 0,
                    "name": vector_name,
                    "alias": "selected_feature",
                    "feature_id": feature_id,
                    "layer_id": layer_id,
                    "geojson_type": "Feature",
                }
            ]
        ),
    )

    sandbox_entry.main()

    result_path = output_dir / "result.tif"
    assert result_path.exists()
    with rasterio.open(result_path) as result:
        np.testing.assert_array_equal(
            result.read(1),
            np.full((2, 2), 7, dtype=np.uint8),
        )


def test_runtime_allows_vector_analysis_without_forcing_an_output(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    script_dir = tmp_path / "scripts"
    input_dir.mkdir()
    output_dir.mkdir()
    script_dir.mkdir()

    vector_name = "selected.geojson"
    (input_dir / vector_name).write_text(
        json.dumps(
            {
                "id": "feature-1",
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [116.3, 39.9]},
                "properties": {"score": 8},
            }
        ),
        encoding="utf-8",
    )
    script_path = script_dir / "user_code.py"
    script_path.write_text(
        "print(features[0]['properties']['score'])",
        encoding="utf-8",
    )

    monkeypatch.setattr(sandbox_entry, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(sandbox_entry, "OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(sandbox_entry, "SCRIPT_PATH", str(script_path))
    monkeypatch.setenv("OUTPUT_FILENAME", "unused.tif")
    monkeypatch.setenv("SANDBOX_INPUT_MAP", "[]")
    monkeypatch.setenv(
        "SANDBOX_VECTOR_MAP",
        json.dumps([{"index": 0, "name": vector_name, "feature_id": "feature-1"}]),
    )

    sandbox_entry.main()

    assert list(Path(output_dir).iterdir()) == []
