import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from functions.implement.change_ops import band_diff, band_ratio, index_diff


def _write_raster(path, data, *, transform=None, valid_mask=None):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:3857",
        transform=transform or from_origin(0, data.shape[0], 1, 1),
    ) as dst:
        dst.write(np.asarray(data, dtype=np.float32), 1)
        if valid_mask is not None:
            dst.write_mask(np.asarray(valid_mask, dtype=np.uint8) * 255)


@pytest.mark.parametrize(
    ("operation", "expected_value"),
    [
        (band_diff, 2.0),
        (band_ratio, 3.0),
    ],
)
def test_change_operations_align_grids_and_intersect_valid_pixels(
    tmp_path,
    operation,
    expected_value,
):
    t1 = tmp_path / "t1.tif"
    t2 = tmp_path / "t2.tif"
    output = tmp_path / f"{operation.__name__}.tif"
    output_mask = tmp_path / f"{operation.__name__}_mask.tif"
    _write_raster(t1, np.ones((3, 3), dtype=np.float32))
    _write_raster(
        t2,
        np.full((2, 2), 3, dtype=np.float32),
        transform=from_origin(1, 2, 1, 1),
    )

    result = operation(
        str(t1),
        str(t2),
        str(output),
        str(output_mask),
        threshold=0.1,
    )

    expected_valid = np.zeros((3, 3), dtype=bool)
    expected_valid[1:, 1:] = True
    with rasterio.open(output) as raster:
        valid = raster.dataset_mask() > 0
        np.testing.assert_array_equal(valid, expected_valid)
        np.testing.assert_allclose(
            raster.read(1)[valid],
            expected_value,
            atol=1e-5,
        )
        assert raster.nodata == -9999
    with rasterio.open(output_mask) as mask_raster:
        np.testing.assert_array_equal(
            mask_raster.dataset_mask() > 0,
            expected_valid,
        )
        assert int(mask_raster.read(1).sum()) == 4
    assert result["change_pixel_count"] == 4


def test_index_diff_propagates_validity_from_all_four_inputs(tmp_path):
    paths = [tmp_path / f"band_{index}.tif" for index in range(4)]
    validity = [
        np.array([[True, True], [True, True]]),
        np.array([[True, False], [True, True]]),
        np.array([[True, True], [False, True]]),
        np.array([[True, True], [True, False]]),
    ]
    values = [1.0, 3.0, 2.0, 8.0]
    for path, value, valid in zip(paths, values, validity):
        _write_raster(
            path,
            np.full((2, 2), value, dtype=np.float32),
            valid_mask=valid,
        )

    output = tmp_path / "index_diff.tif"
    index_diff(
        *(str(path) for path in paths),
        output_diff_path=str(output),
    )

    with rasterio.open(output) as raster:
        np.testing.assert_array_equal(
            raster.dataset_mask() > 0,
            np.array([[True, False], [False, False]]),
        )
        assert raster.read(1)[0, 0] == pytest.approx(0.1, abs=1e-5)
