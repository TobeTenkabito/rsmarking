from datetime import timezone
import json

from functions.implement.temporal_metadata import extract_temporal_metadata


class TaggedDataset:
    def __init__(self, tags=None, namespaces=None):
        self._tags = tags or {}
        self._namespaces = namespaces or {}

    def tags(self, ns=None):
        if ns is None:
            return self._tags
        return self._namespaces.get(ns, {})

    def tag_namespaces(self):
        return list(self._namespaces)


def test_sentinel_filename_extracts_product_metadata(tmp_path):
    path = tmp_path / "stored.tif"
    path.write_bytes(b"")

    metadata = extract_temporal_metadata(
        str(path),
        source_name=(
            "S2A_MSIL2A_20240618T032141_N0510_R018_"
            "T49QGE_20240618T071212.tif"
        ),
        dataset=TaggedDataset(),
    )

    assert metadata["acquired_at"].isoformat() == "2024-06-18T03:21:41+00:00"
    assert metadata["acquired_at_source"] == "sentinel_filename"
    assert metadata["platform"] == "S2A"
    assert metadata["sensor"] == "MSI"
    assert metadata["processing_level"] == "L2A"
    assert metadata["tile_id"] == "T49QGE"


def test_landsat_tags_preserve_scene_center_time(tmp_path):
    path = tmp_path / "stored.tif"
    path.write_bytes(b"")
    dataset = TaggedDataset(
        {
            "DATE_ACQUIRED": "2024-07-03",
            "SCENE_CENTER_TIME": "03:10:11.123456Z",
            "SPACECRAFT_ID": "LANDSAT_9",
            "SENSOR_ID": "OLI_TIRS",
        }
    )

    metadata = extract_temporal_metadata(
        str(path),
        source_name="renamed.tif",
        dataset=dataset,
    )

    assert metadata["acquired_at"].date().isoformat() == "2024-07-03"
    assert metadata["acquired_at"].hour == 3
    assert metadata["acquired_at"].tzinfo == timezone.utc
    assert metadata["acquired_at_source"] == "raster_tag"
    assert metadata["platform"] == "LANDSAT_9"


def test_stac_sidecar_has_priority_over_filename(tmp_path):
    path = tmp_path / "scene_20230101.tif"
    path.write_bytes(b"")
    sidecar = tmp_path / "scene_20230101.stac.json"
    sidecar.write_text(
        json.dumps(
            {
                "id": "product-1",
                "properties": {
                    "datetime": "2024-08-09T10:11:12Z",
                    "platform": "sentinel-2b",
                    "instruments": ["msi"],
                    "processing:level": "L2A",
                    "mgrs:tile": "49QGE",
                },
            }
        ),
        encoding="utf-8",
    )

    metadata = extract_temporal_metadata(
        str(path),
        source_name=path.name,
        dataset=TaggedDataset({"TIFFTAG_DATETIME": "2022:01:01 00:00:00"}),
    )

    assert metadata["acquired_at"].isoformat() == "2024-08-09T10:11:12+00:00"
    assert metadata["acquired_at_source"] == "stac"
    assert metadata["acquired_at_confidence"] == 1.0
    assert metadata["product_id"] == "product-1"


def test_unknown_temporal_metadata_never_uses_file_timestamp(tmp_path):
    path = tmp_path / "arbitrary.tif"
    path.write_bytes(b"")

    metadata = extract_temporal_metadata(
        str(path),
        source_name="arbitrary.tif",
        dataset=TaggedDataset(),
    )

    assert metadata["acquired_at"] is None
    assert metadata["acquired_at_source"] == "unknown"
    assert metadata["acquired_at_confidence"] == 0.0
