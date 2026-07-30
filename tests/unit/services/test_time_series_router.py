from datetime import timezone

import pytest
from pydantic import ValidationError

from services.data_service.routers.time_series_router import TemporalMetadataUpdate


def test_temporal_metadata_update_normalizes_naive_timestamps_to_utc():
    payload = TemporalMetadataUpdate(acquired_at="2024-06-18T03:21:41")

    assert payload.acquired_at is not None
    assert payload.acquired_at.tzinfo == timezone.utc


def test_temporal_metadata_update_rejects_reversed_range():
    with pytest.raises(ValidationError, match="must not be before"):
        TemporalMetadataUpdate(
            acquired_at="2024-06-19T00:00:00Z",
            acquired_at_end="2024-06-18T00:00:00Z",
        )
