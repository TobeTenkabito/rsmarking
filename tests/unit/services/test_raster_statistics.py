import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from services.data_service.raster_statistics import compute_raster_statistics


def _write_test_raster(path):
    data = np.array(
        [
            [[1, 2, 3], [4, -9999, 6]],
            [[10, 20, 30], [40, 50, 60]],
        ],
        dtype=np.float32,
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=3,
        count=2,
        dtype="float32",
        nodata=-9999,
        transform=from_origin(0, 2, 1, 1),
    ) as dst:
        dst.write(data)


def test_compute_raster_statistics_ignores_nodata(tmp_path):
    raster_path = tmp_path / "stats.tif"
    _write_test_raster(raster_path)

    stats = compute_raster_statistics(str(raster_path), bins=5, max_size=128)

    assert stats["width"] == 3
    assert stats["height"] == 2
    assert stats["band_count"] == 2
    assert stats["sample"]["is_full_resolution"] is True

    band = stats["bands"][0]
    assert band["index"] == 1
    assert band["valid_count"] == 5
    assert band["nodata_count"] == 1
    assert band["valid_percent"] == pytest.approx(83.333333, rel=1e-5)
    assert band["min"] == 1
    assert band["max"] == 6
    assert band["mean"] == pytest.approx(3.2)
    assert len(band["histogram"]["bins"]) == 5


def test_compute_raster_statistics_validates_band_indices(tmp_path):
    raster_path = tmp_path / "stats.tif"
    _write_test_raster(raster_path)

    with pytest.raises(ValueError):
        compute_raster_statistics(str(raster_path), band_indices=[3])
