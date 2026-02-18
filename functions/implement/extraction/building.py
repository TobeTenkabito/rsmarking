import numpy as np
from ..spectral_indices import calculate_ndbi_array, calculate_ndvi_array


def extract_building(bands: list[np.ndarray], threshold: float) -> np.ndarray:
    if len(bands) < 2:
        raise ValueError("Building extraction requires at least 2 bands")

    swir, nir = bands[0], bands[1]
    ndbi = calculate_ndbi_array(swir, nir)
    building_mask = (ndbi > threshold)

    if len(bands) == 3:
        red = bands[2]
        ndvi = calculate_ndvi_array(red, nir)
        building_mask = building_mask & (ndvi < 0.2)

    return building_mask.astype('uint8')
