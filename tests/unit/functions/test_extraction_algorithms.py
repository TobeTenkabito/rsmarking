import numpy as np
import pytest

from functions.implement.extraction import (
    extract_building,
    extract_cloud,
    extract_vegetation,
    extract_water,
)


def test_vegetation_ndvi_extracts_high_nir_pixels():
    red = np.array([[0.2, 0.6], [0.3, 0.4]], dtype=np.float32)
    nir = np.array([[0.8, 0.4], [0.7, 0.4]], dtype=np.float32)

    mask = extract_vegetation([red, nir], threshold=0.25)

    assert mask.dtype == np.uint8
    np.testing.assert_array_equal(mask, [[1, 0], [1, 0]])


def test_water_mndwi_and_otsu_return_uint8_masks():
    green = np.array([[0.8, 0.2], [0.7, 0.1]], dtype=np.float32)
    swir = np.array([[0.1, 0.5], [0.2, 0.4]], dtype=np.float32)

    mndwi_mask = extract_water([green, swir], threshold=0.0, mode="mndwi")
    otsu_mask = extract_water([green, swir], threshold=0.0, mode="otsu")

    assert mndwi_mask.dtype == np.uint8
    assert otsu_mask.dtype == np.uint8
    np.testing.assert_array_equal(mndwi_mask, [[1, 0], [1, 0]])
    assert otsu_mask.shape == green.shape


def test_building_ndbi_preserves_legacy_two_band_behavior():
    swir = np.array([[0.3, 0.6], [0.5, 0.2]], dtype=np.float32)
    nir = np.array([[0.4, 0.3], [0.3, 0.3]], dtype=np.float32)

    mask = extract_building([swir, nir], threshold=0.0, mode="ndbi")

    assert mask.dtype == np.uint8
    np.testing.assert_array_equal(mask, [[0, 1], [1, 0]])


def test_building_ibi_requires_four_bands_and_returns_shape():
    swir = np.full((8, 8), 0.35, dtype=np.float32)
    nir = np.full((8, 8), 0.25, dtype=np.float32)
    red = np.full((8, 8), 0.22, dtype=np.float32)
    green = np.full((8, 8), 0.18, dtype=np.float32)
    swir[2:6, 2:6] = 0.65
    nir[2:6, 2:6] = 0.30

    mask = extract_building([swir, nir, red, green], threshold=0.0, mode="ibi")

    assert mask.dtype == np.uint8
    assert mask.shape == swir.shape
    assert mask.sum() > 0


def test_cloud_default_threshold_and_fmask_modes():
    blue = np.full((8, 8), 0.08, dtype=np.float32)
    green = np.full((8, 8), 0.08, dtype=np.float32)
    red = np.full((8, 8), 0.08, dtype=np.float32)
    nir = np.full((8, 8), 0.20, dtype=np.float32)
    swir1 = np.full((8, 8), 0.08, dtype=np.float32)

    blue[2:6, 2:6] = 0.62
    green[2:6, 2:6] = 0.60
    red[2:6, 2:6] = 0.58
    nir[2:6, 2:6] = 0.48
    swir1[2:6, 2:6] = 0.34

    threshold_mask = extract_cloud([blue, swir1], threshold=0.2, mode="default")
    fmask = extract_cloud([blue, green, red, nir, swir1], mode="fmask")

    assert threshold_mask.dtype == np.uint8
    assert fmask.dtype == np.uint8
    assert threshold_mask.sum() == 16
    assert fmask.sum() == 16


def test_extraction_unknown_modes_raise_clear_errors():
    band = np.ones((2, 2), dtype=np.float32)

    with pytest.raises(ValueError, match="Unknown cloud extraction mode"):
        extract_cloud([band], mode="not-a-mode")

    with pytest.raises(ValueError, match="Unknown building extraction mode"):
        extract_building([band, band], mode="not-a-mode")
