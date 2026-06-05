import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from functions.implement.texture_features import texture_feature_analysis


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


def test_glcm_contrast_is_zero_for_constant_image(tmp_path):
    source = tmp_path / "constant.tif"
    output = tmp_path / "glcm.tif"
    _write_raster(source, np.ones((5, 5), dtype=np.float32) * 7)

    result = texture_feature_analysis(
        str(source),
        str(output),
        texture_type="glcm",
        gray_levels=8,
        window_size=3,
        glcm_property="contrast",
    )

    with rasterio.open(output) as ds:
        contrast = ds.read(1)
        assert ds.count == 1
        assert ds.tags()["TEXTURE_FEATURE_ANALYSIS"] == "true"
        assert ds.tags()["TEXTURE_TYPE"] == "glcm"
        np.testing.assert_allclose(contrast, np.zeros((5, 5), dtype=np.float32))
    assert result["texture_type"] == "glcm"
    assert result["glcm_property"] == "contrast"


def test_local_statistics_mean_uses_window_values(tmp_path):
    source = tmp_path / "gradient.tif"
    output = tmp_path / "mean.tif"
    data = np.arange(25, dtype=np.float32).reshape(5, 5)
    _write_raster(source, data)

    result = texture_feature_analysis(
        str(source),
        str(output),
        texture_type="local_statistics",
        window_size=3,
        local_stat="mean",
    )

    with rasterio.open(output) as ds:
        mean = ds.read(1)
        assert mean[2, 2] == pytest.approx(float(data[1:4, 1:4].mean()))
    assert result["texture_type"] == "local_statistics"
    assert result["local_stat"] == "mean"


def test_gabor_filter_writes_finite_response(tmp_path):
    source = tmp_path / "stripes.tif"
    output = tmp_path / "gabor.tif"
    data = np.tile([0, 1, 0, 1, 0], (5, 1)).astype(np.float32)
    _write_raster(source, data)

    result = texture_feature_analysis(
        str(source),
        str(output),
        texture_type="gabor",
        gabor_frequency=0.25,
        gabor_sigma=1.5,
    )

    with rasterio.open(output) as ds:
        response = ds.read(1)
        assert np.isfinite(response).all()
        assert response.max() > 0
        assert ds.tags()["TEXTURE_TYPE"] == "gabor"
    assert result["gabor_kernel_size"] >= 3


def test_lbp_constant_image_sets_all_neighbor_bits(tmp_path):
    source = tmp_path / "constant.tif"
    output = tmp_path / "lbp.tif"
    _write_raster(source, np.ones((5, 5), dtype=np.float32) * 3)

    result = texture_feature_analysis(
        str(source),
        str(output),
        texture_type="lbp",
        lbp_radius=1,
        lbp_points=8,
    )

    with rasterio.open(output) as ds:
        lbp = ds.read(1)
        np.testing.assert_allclose(lbp, np.full((5, 5), 255, dtype=np.float32))
    assert result["texture_type"] == "lbp"
    assert result["lbp_points"] == 8
