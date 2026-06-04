import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from functions.implement.raster_transforms import raster_transform_analysis


def _write_raster(path, data, dtype="float32"):
    if data.ndim == 2:
        data = data[np.newaxis, ...]

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[1],
        width=data.shape[2],
        count=data.shape[0],
        dtype=dtype,
        crs="EPSG:3857",
        transform=from_origin(0, data.shape[1], 1, 1),
    ) as dst:
        dst.write(data.astype(dtype))


def test_fourier_delta_has_flat_magnitude_spectrum(tmp_path):
    source = tmp_path / "delta.tif"
    output = tmp_path / "fourier.tif"
    data = np.zeros((4, 4), dtype=np.float32)
    data[1, 2] = 1.0
    _write_raster(source, data)

    result = raster_transform_analysis(
        str(source),
        str(output),
        transform_type="fourier",
        fourier_output="magnitude",
    )

    with rasterio.open(output) as ds:
        spectrum = ds.read(1)
        assert ds.count == 1
        assert ds.tags()["RASTER_TRANSFORM_ANALYSIS"] == "true"
        np.testing.assert_allclose(spectrum, np.full((4, 4), np.log1p(1.0), dtype=np.float32))
    assert result["transform_type"] == "fourier"


def test_haar_wavelet_detail_energy_is_zero_for_constant_image(tmp_path):
    source = tmp_path / "constant.tif"
    output = tmp_path / "wavelet.tif"
    _write_raster(source, np.ones((4, 4), dtype=np.float32) * 7)

    result = raster_transform_analysis(
        str(source),
        str(output),
        transform_type="wavelet",
        wavelet_output="detail_energy",
        wavelet_level=1,
    )

    with rasterio.open(output) as ds:
        detail = ds.read(1)
        assert ds.count == 1
        np.testing.assert_allclose(detail, np.zeros((4, 4), dtype=np.float32))
    assert result["wavelet_output"] == "detail_energy"


def test_pca_writes_requested_components_and_variance_ratios(tmp_path):
    source = tmp_path / "stack.tif"
    output = tmp_path / "pca.tif"
    base = np.arange(16, dtype=np.float32).reshape(4, 4)
    stack = np.stack([base, base * 2, base * -1])
    _write_raster(source, stack)

    result = raster_transform_analysis(
        str(source),
        str(output),
        transform_type="pca",
        pca_components=2,
    )

    with rasterio.open(output) as ds:
        assert ds.count == 2
        assert ds.read().shape == (2, 4, 4)
    assert result["transform_type"] == "pca"
    assert result["pca_components"] == 2
    assert result["explained_variance_ratio"][0] == pytest.approx(1.0)
    assert result["explained_variance_ratio"][1] == pytest.approx(0.0, abs=1e-6)
