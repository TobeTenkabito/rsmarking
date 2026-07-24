import numpy as np
import pytest

pytest.importorskip("osgeo")
rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from services.data_service import processor as processor_module
from services.data_service.processor import RasterProcessor


def _write_raster(
    path,
    data,
    *,
    descriptions=None,
    nodata=None,
    valid_mask=None,
    transform=None,
):
    if data.ndim == 2:
        data = data[np.newaxis, ...]

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[1],
        width=data.shape[2],
        count=data.shape[0],
        dtype=str(data.dtype),
        crs="EPSG:4326",
        transform=transform or from_origin(0, data.shape[1], 1, 1),
        nodata=nodata,
    ) as dst:
        dst.write(data)
        if valid_mask is not None:
            dst.write_mask(np.asarray(valid_mask, dtype=np.uint8) * 255)
        if descriptions:
            for band_index, description in enumerate(descriptions, start=1):
                dst.set_band_description(band_index, description)


def test_parse_var_tokens_keeps_band_tokens_and_ignores_numexpr_functions():
    tokens = RasterProcessor._parse_var_tokens("where(A_2 > 0, sqrt(A_2), B + GREEN_1_3)")

    assert tokens == {
        "A_2": ("A", [2]),
        "B": ("B", []),
        "GREEN_1_3": ("GREEN", [1, 3]),
    }


@pytest.mark.parametrize(
    ("band_counts", "expected"),
    [
        ([2, 2], 2),
        ([1, 4], 4),
        ([1, 1, 1], 1),
    ],
)
def test_resolve_output_bands_allows_equal_counts_and_single_band_broadcast(
    band_counts,
    expected,
):
    arrays = {
        f"token_{index}": np.zeros((count, 2, 2), dtype=np.float32)
        for index, count in enumerate(band_counts)
    }

    assert RasterProcessor._resolve_output_bands(arrays) == expected


def test_resolve_output_bands_rejects_multiple_non_singleton_counts():
    arrays = {
        "A": np.zeros((2, 2, 2), dtype=np.float32),
        "B": np.zeros((3, 2, 2), dtype=np.float32),
        "C": np.zeros((1, 2, 2), dtype=np.float32),
    }

    with pytest.raises(ValueError):
        RasterProcessor._resolve_output_bands(arrays)


def test_raster_calculator_broadcasts_single_selected_band(tmp_path, monkeypatch):
    source_a = tmp_path / "a.tif"
    source_b = tmp_path / "b.tif"
    output = tmp_path / "calculator.tif"
    _write_raster(
        source_a,
        np.stack(
            [
                np.full((2, 2), 1, dtype=np.float32),
                np.full((2, 2), 2, dtype=np.float32),
            ]
        ),
    )
    _write_raster(source_b, np.full((2, 2), 10, dtype=np.float32))
    monkeypatch.setattr(processor_module, "build_raster_overviews", lambda path: True)

    RasterProcessor.run_raster_calculator(
        {"A": str(source_a), "B": str(source_b)},
        "A + B_1",
        str(output),
    )

    with rasterio.open(output) as result:
        assert result.count == 2
        np.testing.assert_array_equal(result.read(1), np.full((2, 2), 11, dtype=np.float32))
        np.testing.assert_array_equal(result.read(2), np.full((2, 2), 12, dtype=np.float32))


def test_raster_calculator_intersects_input_validity_masks(tmp_path, monkeypatch):
    source_a = tmp_path / "masked_a.tif"
    source_b = tmp_path / "masked_b.tif"
    output = tmp_path / "masked_calculator.tif"
    _write_raster(
        source_a,
        np.ones((2, 2), dtype=np.float32),
        valid_mask=np.array([[True, True], [False, False]]),
    )
    _write_raster(
        source_b,
        np.full((2, 2), 10, dtype=np.float32),
        valid_mask=np.array([[True, False], [True, False]]),
    )
    monkeypatch.setattr(processor_module, "build_raster_overviews", lambda path: True)

    RasterProcessor.run_raster_calculator(
        {"A": str(source_a), "B": str(source_b)},
        "A + B",
        str(output),
    )

    with rasterio.open(output) as result:
        assert result.nodata == -9999
        np.testing.assert_array_equal(
            result.dataset_mask() > 0,
            np.array([[True, False], [False, False]]),
        )
        assert result.read(1)[0, 0] == 11
        assert np.all(result.read(1)[~(result.dataset_mask() > 0)] == -9999)


def test_raster_calculator_distinguishes_implicit_background_from_valid_zero(
    tmp_path,
    monkeypatch,
):
    implicit = tmp_path / "implicit_zero.tif"
    explicit = tmp_path / "explicit_zero.tif"
    implicit_output = tmp_path / "implicit_result.tif"
    explicit_output = tmp_path / "explicit_result.tif"
    data = np.array([[0, 2]], dtype=np.float32)
    _write_raster(implicit, data)
    _write_raster(
        explicit,
        data,
        valid_mask=np.ones((1, 2), dtype=bool),
    )
    monkeypatch.setattr(processor_module, "build_raster_overviews", lambda path: True)

    RasterProcessor.run_raster_calculator(
        {"A": str(implicit)},
        "A * 2",
        str(implicit_output),
    )
    RasterProcessor.run_raster_calculator(
        {"A": str(explicit)},
        "A * 2",
        str(explicit_output),
    )

    with rasterio.open(implicit_output) as result:
        np.testing.assert_array_equal(
            result.dataset_mask() > 0,
            np.array([[False, True]]),
        )
    with rasterio.open(explicit_output) as result:
        np.testing.assert_array_equal(
            result.dataset_mask() > 0,
            np.array([[True, True]]),
        )
        np.testing.assert_array_equal(
            result.read(1),
            np.array([[0, 4]], dtype=np.float32),
        )


def test_two_band_index_aligns_grid_and_masks_invalid_pixels(tmp_path, monkeypatch):
    red = tmp_path / "red.tif"
    nir = tmp_path / "nir.tif"
    output = tmp_path / "ndvi.tif"
    _write_raster(
        red,
        np.ones((3, 3), dtype=np.float32),
        valid_mask=np.ones((3, 3), dtype=bool),
    )
    _write_raster(
        nir,
        np.full((2, 2), 3, dtype=np.float32),
        transform=from_origin(1, 2, 1, 1),
        valid_mask=np.ones((2, 2), dtype=bool),
    )
    monkeypatch.setattr(processor_module, "build_raster_overviews", lambda path: True)

    RasterProcessor.calculate_ndvi(str(red), str(nir), str(output))

    with rasterio.open(output) as result:
        valid = result.dataset_mask() > 0
        expected_valid = np.zeros((3, 3), dtype=bool)
        expected_valid[1:, 1:] = True
        np.testing.assert_array_equal(valid, expected_valid)
        np.testing.assert_allclose(result.read(1)[valid], 0.5)
        assert np.all(result.read(1)[~valid] == -9999)


def test_query_spectrum_uses_band_descriptions_and_marks_nodata(tmp_path):
    source = tmp_path / "spectrum.tif"
    _write_raster(
        source,
        np.array(
            [
                [[5, 6], [7, 8]],
                [[-9999, 2], [3, 4]],
            ],
            dtype=np.float32,
        ),
        descriptions=["Red", "NIR"],
        nodata=-9999,
    )

    result = RasterProcessor.query_spectrum(str(source), lng=0.5, lat=1.5)

    assert result["bands"] == [
        {"index": 1, "name": "Red", "value": 5.0},
        {"index": 2, "name": "NIR", "value": None},
    ]
    assert result["has_nodata"] is True
    assert result["coordinate"] == {"lng": 0.5, "lat": 1.5}
