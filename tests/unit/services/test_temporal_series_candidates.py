from datetime import datetime, timezone

from services.data_service.temporal_series import build_time_series_candidates


def _record(index_id, **overrides):
    value = {
        "index_id": index_id,
        "platform": "S2A",
        "sensor": "MSI",
        "processing_level": "L2A",
        "tile_id": "T49QGE",
        "bands": 4,
        "crs": "EPSG:32649",
        "width": 100,
        "height": 100,
        "resolution_x": 10,
        "resolution_y": 10,
        "bounds": [500000, 0, 501000, 1000],
        "bounds_wgs84": [115.0, 30.0, 115.01, 30.01],
        "center": [115.005, 30.005],
        "acquired_at": None,
        "acquired_at_source": "unknown",
        "acquired_at_confidence": 0.0,
    }
    value.update(overrides)
    return value


def test_candidates_group_and_sort_without_user_confirmation():
    later = datetime(2024, 6, 20, tzinfo=timezone.utc)
    earlier = datetime(2024, 6, 10, tzinfo=timezone.utc)
    candidates = build_time_series_candidates(
        [
            _record(
                2,
                acquired_at=later,
                acquired_at_source="stac",
                acquired_at_confidence=1.0,
            ),
            _record(3),
            _record(
                1,
                acquired_at=earlier,
                acquired_at_source="filename",
                acquired_at_confidence=0.55,
            ),
        ]
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["raster_ids"] == [1, 2, 3]
    assert candidate["input_count"] == 3
    assert candidate["dated_input_count"] == 2
    assert candidate["date_coverage"] == 2 / 3
    assert "monthly_composite" in candidate["suggested_operations"]
    assert any("unknown" in warning for warning in candidate["warnings"])
    assert any("low-confidence" in warning for warning in candidate["warnings"])


def test_candidates_separate_incompatible_product_identity():
    candidates = build_time_series_candidates(
        [
            _record(1),
            _record(
                2,
                platform="Landsat-9",
                sensor="OLI_TIRS",
                processing_level="L2SP",
                tile_id="122/034",
                bands=7,
            ),
        ]
    )

    assert len(candidates) == 2
    assert sorted(candidate["input_count"] for candidate in candidates) == [1, 1]


def test_candidate_reports_automatic_grid_alignment():
    acquired = datetime(2024, 6, 10, tzinfo=timezone.utc)
    candidates = build_time_series_candidates(
        [
            _record(1, acquired_at=acquired),
            _record(2, width=200, height=200, resolution_x=5, resolution_y=5),
        ]
    )

    assert candidates[0]["automatic_alignment"] is True
    assert any("automatically aligned" in warning for warning in candidates[0]["warnings"])


def test_partial_product_metadata_does_not_merge_different_regions():
    candidates = build_time_series_candidates(
        [
            _record(1, tile_id=None),
            _record(
                2,
                tile_id=None,
                bounds=[600000, 0, 601000, 1000],
                bounds_wgs84=[116.0, 30.0, 116.01, 30.01],
                center=[116.005, 30.005],
            ),
        ]
    )

    assert len(candidates) == 2


def test_records_without_product_metadata_use_spatial_coverage():
    common = {
        "platform": None,
        "sensor": None,
        "processing_level": None,
        "tile_id": None,
    }
    candidates = build_time_series_candidates(
        [
            _record(1, **common),
            _record(2, **common),
            _record(
                3,
                **common,
                bounds=[600000, 0, 601000, 1000],
                bounds_wgs84=[116.0, 30.0, 116.01, 30.01],
                center=[116.005, 30.005],
            ),
        ]
    )

    assert sorted(candidate["input_count"] for candidate in candidates) == [1, 2]
