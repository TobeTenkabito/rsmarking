import numpy as np

from functions.implement.spectral_indices import (
    calculate_mndwi_array,
    calculate_ndbi_array,
    calculate_ndvi_array,
    calculate_ndwi_array,
)


def test_normalized_indices_match_expected_values():
    red = np.array([[0.2, 0.4]], dtype=np.float32)
    nir = np.array([[0.6, 0.2]], dtype=np.float32)
    green = np.array([[0.5, 0.1]], dtype=np.float32)
    swir = np.array([[0.1, 0.3]], dtype=np.float32)

    np.testing.assert_allclose(calculate_ndvi_array(red, nir), [[0.5, -0.33333334]], rtol=1e-6)
    np.testing.assert_allclose(calculate_ndwi_array(green, nir), [[-0.09090909, -0.33333334]], rtol=1e-6)
    np.testing.assert_allclose(calculate_ndbi_array(swir, nir), [[-0.71428573, 0.2]], rtol=1e-6)
    np.testing.assert_allclose(calculate_mndwi_array(green, swir), [[0.6666666, -0.5]], rtol=1e-6)


def test_normalized_indices_sanitize_zero_division_and_invalid_values():
    a = np.array([[0.0, np.nan, np.inf]], dtype=np.float32)
    b = np.array([[0.0, 1.0, np.inf]], dtype=np.float32)

    result = calculate_mndwi_array(a, b)

    assert result.dtype == np.float32
    assert np.isfinite(result).all()
    np.testing.assert_array_equal(result, np.array([[0.0, 0.0, 0.0]], dtype=np.float32))
