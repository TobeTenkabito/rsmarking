import numpy as np
import logging

logger = logging.getLogger("functions.spectral_indices")


def calculate_ndvi_array(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    red = red.astype('float32')
    nir = nir.astype('float32')
    with np.errstate(divide='ignore', invalid='ignore'):
        ndvi = (nir - red) / (nir + red)
        return np.nan_to_num(ndvi, nan=0.0, posinf=1.0, neginf=-1.0)


def calculate_ndwi_array(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    green = green.astype('float32')
    nir = nir.astype('float32')
    with np.errstate(divide='ignore', invalid='ignore'):
        ndwi = (green - nir) / (green + nir)
        return np.nan_to_num(ndwi, nan=0.0, posinf=1.0, neginf=-1.0)


def calculate_ndbi_array(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
    swir = swir.astype('float32')
    nir = nir.astype('float32')
    with np.errstate(divide='ignore', invalid='ignore'):
        ndbi = (swir - nir) / (swir + nir)
        return np.nan_to_num(ndbi, nan=0.0, posinf=1.0, neginf=-1.0)


def calculate_mndwi_array(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    green = green.astype('float32')
    swir = swir.astype('float32')
    with np.errstate(divide='ignore', invalid='ignore'):
        mndwi = (green - swir) / (green + swir)
        return np.nan_to_num(mndwi, nan=0.0, posinf=1.0, neginf=-1.0)
      
