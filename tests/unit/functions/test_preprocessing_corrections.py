import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from functions.implement.geometric import geometric_correction
from functions.implement.radiometric import radiometric_calibration


def _write_raster(path, data, transform=None, crs="EPSG:3857"):
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[1],
        width=data.shape[2],
        count=data.shape[0],
        dtype="float32",
        crs=crs,
        transform=transform or from_origin(10, 20, 2, 2),
    ) as dst:
        dst.write(data.astype("float32"))


def test_radiometric_calibration_scale_offset(tmp_path):
    source = tmp_path / "source.tif"
    output = tmp_path / "radiometric.tif"
    _write_raster(source, np.array([[0, 10], [20, 30]], dtype=np.float32))

    result = radiometric_calibration(
        str(source),
        str(output),
        calibration_type="scale",
        scale_factor=0.1,
        offset=1.0,
    )

    with rasterio.open(output) as calibrated:
        data = calibrated.read(1)
        assert calibrated.dtypes[0] == "float32"
        np.testing.assert_allclose(data, np.array([[1, 2], [3, 4]], dtype=np.float32))
    assert result["operation"] == "radiometric_calibration"
    assert result["bands"][0]["mode"] == "scale"


def test_geometric_correction_applies_shift_to_transform(tmp_path):
    source = tmp_path / "source.tif"
    output = tmp_path / "geometric.tif"
    transform = from_origin(10, 20, 2, 2)
    _write_raster(source, np.ones((3, 3), dtype=np.float32), transform=transform)

    result = geometric_correction(
        str(source),
        str(output),
        shift_x=5,
        shift_y=-3,
        resampling_method="nearest",
    )

    with rasterio.open(output) as corrected:
        assert corrected.transform.c == pytest.approx(15)
        assert corrected.transform.f == pytest.approx(17)
        assert corrected.width == 3
        assert corrected.height == 3
    assert result["operation"] == "geometric_correction"
    assert result["method"] == "affine"
