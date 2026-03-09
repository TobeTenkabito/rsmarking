import numpy as np
import logging

logger = logging.getLogger("functions.spectral_indices")


def _normalized_difference(
    band1: np.ndarray,
    band2: np.ndarray,
) -> np.ndarray:
    """
    计算标准归一化差值指数：
        (band1 - band2) / (band1 + band2)
    统一处理：
    - float32 转换
    - 除零保护
    - NaN / Inf 清理
    """
    band1 = band1.astype("float32", copy=False)
    band2 = band2.astype("float32", copy=False)

    with np.errstate(divide="ignore", invalid="ignore"):
        result = (band1 - band2) / (band1 + band2)

    return np.nan_to_num(
        result,
        nan=0.0,
        posinf=1.0,
        neginf=-1.0,
    )


def calculate_ndvi_array(red: np.ndarray, nir: np.ndarray,) -> np.ndarray:
    """
    NDVI = (NIR - RED) / (NIR + RED)
    """
    return _normalized_difference(nir, red)


def calculate_ndwi_array(green: np.ndarray, nir: np.ndarray,) -> np.ndarray:
    """
    NDWI = (GREEN - NIR) / (GREEN + NIR)
    """
    return _normalized_difference(green, nir)


def calculate_ndbi_array(swir: np.ndarray, nir: np.ndarray,) -> np.ndarray:
    """
    NDBI = (SWIR - NIR) / (SWIR + NIR)
    """
    return _normalized_difference(swir, nir)


def calculate_mndwi_array(green: np.ndarray, swir: np.ndarray,) -> np.ndarray:
    """
    MNDWI = (GREEN - SWIR) / (GREEN + SWIR)
    """
    return _normalized_difference(green, swir)
