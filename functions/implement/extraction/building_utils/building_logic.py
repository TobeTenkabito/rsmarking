from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from ...spectral_indices import (
    calculate_mndwi_array,
    calculate_ndbi_array,
    calculate_ndvi_array,
)


EPSILON = 1e-10


@dataclass
class BuildingParams:
    ndbi_threshold: float = 0.0
    ibi_threshold: float = 0.0
    score_threshold: float = 0.55
    ndvi_max: float = 0.2
    mndwi_max: float = 0.0
    min_component_size: int = 12
    apply_morphology: bool = True


def normalize_reflectance(arr: np.ndarray) -> np.ndarray:
    data = arr.astype("float32", copy=False)
    finite = np.isfinite(data)
    if not np.any(finite):
        return np.zeros_like(data, dtype="float32")

    valid = data[finite]
    max_value = float(np.nanmax(valid))

    if max_value <= 1.0:
        scaled = data
    elif max_value <= 255.0:
        scaled = data / 255.0
    elif max_value <= 12000.0:
        scaled = data / 10000.0
    else:
        scaled = data / 65535.0

    scaled = np.nan_to_num(scaled, nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(scaled, 0.0, 1.0).astype("float32", copy=False)


def _as_reflectance_bands(bands: List[np.ndarray]) -> list[np.ndarray]:
    if not bands:
        raise ValueError("Building extraction requires at least one band")

    first_shape = bands[0].shape
    normalized = []
    for band in bands:
        if band.shape != first_shape:
            raise ValueError("Building extraction bands must have the same shape")
        normalized.append(normalize_reflectance(band))
    return normalized


def _safe_ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        result = numerator / (denominator + EPSILON)
    return np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)


def _clean_mask(mask: np.ndarray, params: BuildingParams) -> np.ndarray:
    if not params.apply_morphology and params.min_component_size <= 1:
        return mask

    try:
        from scipy import ndimage
    except Exception:
        return mask

    cleaned = mask
    if params.apply_morphology:
        structure = np.ones((3, 3), dtype=bool)
        cleaned = ndimage.binary_opening(cleaned, structure=structure)
        cleaned = ndimage.binary_closing(cleaned, structure=structure)
        cleaned = ndimage.binary_fill_holes(cleaned)

    if params.min_component_size > 1:
        labeled, _ = ndimage.label(cleaned)
        sizes = np.bincount(labeled.ravel())
        if sizes.size > 0:
            sizes[0] = 0
            cleaned = sizes[labeled] >= params.min_component_size

    return cleaned


def ndbi_building(
    bands: List[np.ndarray],
    threshold: float | None = None,
    params: BuildingParams | None = None,
) -> np.ndarray:
    if len(bands) < 2:
        raise ValueError("NDBI building extraction requires SWIR and NIR bands")

    params = params or BuildingParams()
    reflectance = _as_reflectance_bands(bands)
    swir, nir = reflectance[0], reflectance[1]
    cutoff = params.ndbi_threshold if threshold is None else threshold

    ndbi = calculate_ndbi_array(swir, nir)
    mask = ndbi > cutoff

    if len(reflectance) >= 3:
        red = reflectance[2]
        ndvi = calculate_ndvi_array(red, nir)
        mask = mask & (ndvi < params.ndvi_max)

    if len(reflectance) >= 4:
        green = reflectance[3]
        mndwi = calculate_mndwi_array(green, swir)
        mask = mask & (mndwi < params.mndwi_max)

    return _clean_mask(mask, params).astype("uint8")


def urban_index_building(
    bands: List[np.ndarray],
    threshold: float | None = None,
    params: BuildingParams | None = None,
) -> np.ndarray:
    if len(bands) < 2:
        raise ValueError("Urban-index building extraction requires SWIR and NIR bands")

    params = params or BuildingParams()
    reflectance = _as_reflectance_bands(bands)
    swir, nir = reflectance[0], reflectance[1]
    cutoff = params.ndbi_threshold if threshold is None else threshold
    ui = calculate_ndbi_array(swir, nir)
    mask = ui > cutoff
    return _clean_mask(mask, params).astype("uint8")


def ibi_building(
    bands: List[np.ndarray],
    threshold: float | None = None,
    params: BuildingParams | None = None,
) -> np.ndarray:
    if len(bands) < 4:
        raise ValueError("IBI building extraction requires SWIR, NIR, Red, and Green bands")

    params = params or BuildingParams()
    reflectance = _as_reflectance_bands(bands)
    swir, nir, red, green = reflectance[:4]

    ndbi = calculate_ndbi_array(swir, nir)
    ndvi = calculate_ndvi_array(red, nir)
    mndwi = calculate_mndwi_array(green, swir)
    background = (ndvi + mndwi) / 2.0
    ibi = _safe_ratio(ndbi - background, ndbi + background)

    cutoff = params.ibi_threshold if threshold is None else threshold
    mask = (ibi > cutoff) & (ndvi < params.ndvi_max) & (mndwi < params.mndwi_max)
    return _clean_mask(mask, params).astype("uint8")


def compute_building_score(
    bands: List[np.ndarray],
    params: BuildingParams | None = None,
) -> np.ndarray:
    if len(bands) < 2:
        raise ValueError("Building score requires at least SWIR and NIR bands")

    params = params or BuildingParams()
    reflectance = _as_reflectance_bands(bands)
    swir, nir = reflectance[0], reflectance[1]

    ndbi = calculate_ndbi_array(swir, nir)
    score = np.clip((ndbi + 1.0) / 2.0, 0, 1) * 0.55

    if len(reflectance) >= 3:
        red = reflectance[2]
        ndvi = calculate_ndvi_array(red, nir)
        score += np.clip((params.ndvi_max - ndvi) / (params.ndvi_max + 1.0), 0, 1) * 0.25
    else:
        score += 0.125

    if len(reflectance) >= 4:
        green = reflectance[3]
        mndwi = calculate_mndwi_array(green, swir)
        score += np.clip((params.mndwi_max - mndwi) / (params.mndwi_max + 1.0), 0, 1) * 0.20
    else:
        score += 0.10

    return np.clip(score, 0.0, 1.0)


def building_score_mask(
    bands: List[np.ndarray],
    threshold: float | None = None,
    params: BuildingParams | None = None,
) -> np.ndarray:
    params = params or BuildingParams()
    cutoff = params.score_threshold if threshold is None else threshold
    score = compute_building_score(bands, params)
    return _clean_mask(score > cutoff, params).astype("uint8")
