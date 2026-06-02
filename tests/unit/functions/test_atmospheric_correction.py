import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from functions.implement.atmospheric_correction import atmospheric_correction


def _write_raster(path, data, *, nodata=None, descriptions=None, tags=None):
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
        transform=from_origin(0, data.shape[1], 1, 1),
        nodata=nodata,
    ) as dst:
        dst.write(data)
        if descriptions:
            for band_index, description in enumerate(descriptions, start=1):
                dst.set_band_description(band_index, description)
        if tags:
            dst.update_tags(**tags)


def test_sentinel2_sen2cor_product_is_scaled_to_reflectance(tmp_path):
    source = tmp_path / "S2A_MSIL2A_scene.tif"
    output = tmp_path / "corrected.tif"
    _write_raster(
        source,
        np.array([[1000, 2000], [0, 10000]], dtype=np.uint16),
        nodata=0,
        descriptions=["B04"],
    )

    result = atmospheric_correction(str(source), str(output), method="auto", sensor="auto")

    with rasterio.open(output) as corrected:
        data = corrected.read(1)
        tags = corrected.tags()

    assert result["method"] == "metadata_scale"
    assert result["sensor"] == "sentinel2"
    assert result["compatibility"] == "Sentinel-2 Sen2Cor"
    assert tags["ATMOSPHERIC_METHOD"] == "metadata_scale"
    assert data[0, 0] == pytest.approx(0.1)
    assert data[0, 1] == pytest.approx(0.2)
    assert data[1, 0] == pytest.approx(-9999.0)
    assert data[1, 1] == pytest.approx(1.0)


def test_dos1_subtracts_dark_object_after_auto_scaling(tmp_path):
    source = tmp_path / "generic_raw.tif"
    output = tmp_path / "dos.tif"
    _write_raster(
        source,
        np.array([[100, 200], [300, 400]], dtype=np.uint16),
    )

    result = atmospheric_correction(
        str(source),
        str(output),
        method="dos1",
        sensor="generic",
        dark_percentile=0.0,
    )

    with rasterio.open(output) as corrected:
        data = corrected.read(1)

    assert result["method"] == "dos1"
    assert result["scale_factor"] == pytest.approx(0.0001)
    np.testing.assert_allclose(
        data,
        np.array([[0.0, 0.01], [0.02, 0.03]], dtype=np.float32),
        atol=1e-6,
    )


def test_quac_normalizes_between_dark_and_bright_percentiles(tmp_path):
    source = tmp_path / "GF_QUAC_input.tif"
    output = tmp_path / "quac.tif"
    _write_raster(
        source,
        np.array([[1000, 3000], [5000, 9000]], dtype=np.uint16),
    )

    result = atmospheric_correction(
        str(source),
        str(output),
        method="quac",
        sensor="gaofen",
        dark_percentile=0.0,
        bright_percentile=100.0,
    )

    with rasterio.open(output) as corrected:
        data = corrected.read(1)

    assert result["method"] == "quac"
    assert result["compatibility"] == "Gaofen FLAASH/QUAC/6S"
    np.testing.assert_allclose(
        data,
        np.array([[0.0, 0.25], [0.5, 1.0]], dtype=np.float32),
        atol=1e-6,
    )
