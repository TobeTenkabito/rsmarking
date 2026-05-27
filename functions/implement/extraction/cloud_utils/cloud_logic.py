from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


EPSILON = 1e-10


@dataclass
class CloudParams:
    blue_threshold: float = 0.25
    swir_threshold: float = 0.18
    brightness_threshold: float = 0.30
    whiteness_max: float = 0.70
    ndvi_max: float = 0.80
    ndsi_max: float = 0.80
    hot_threshold: float = 0.00
    score_threshold: float = 0.55
    min_component_size: int = 9
    apply_morphology: bool = True


def normalize_reflectance(arr: np.ndarray) -> np.ndarray:
    data = np.asarray(arr, dtype=np.float32)
    if data.size == 0:
        return np.zeros_like(data, dtype="float32")

    max_value = float(np.nanmax(data))
    if not np.isfinite(max_value):
        finite = np.isfinite(data)
        if not np.any(finite):
            return np.zeros_like(data, dtype="float32")
        max_value = float(np.max(data[finite]))

    if max_value <= 1.0:
        scaled = data.copy()
    elif max_value <= 255.0:
        scaled = data / 255.0
    elif max_value <= 12000.0:
        scaled = data / 10000.0
    else:
        scaled = data / 65535.0

    np.nan_to_num(scaled, copy=False, nan=0.0, posinf=1.0, neginf=0.0)
    np.clip(scaled, 0.0, 1.0, out=scaled)
    return scaled.astype("float32", copy=False)


def _as_reflectance_bands(
    bands: List[np.ndarray],
    limit: int | None = None,
) -> list[np.ndarray]:
    if not bands:
        raise ValueError("Cloud extraction requires at least one band")

    first_shape = bands[0].shape
    for band in bands:
        if band.shape != first_shape:
            raise ValueError("Cloud extraction bands must have the same shape")

    selected = bands[:limit] if limit is not None else bands
    return [normalize_reflectance(band) for band in selected]


def _normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    out_shape = np.broadcast_shapes(a.shape, b.shape)

    result = np.empty(out_shape, dtype=np.float32)
    denominator = np.empty(out_shape, dtype=np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        np.subtract(a, b, out=result)
        np.add(a, b, out=denominator)
        np.add(denominator, EPSILON, out=denominator)
        np.divide(result, denominator, out=result)
    return np.nan_to_num(result, copy=False, nan=0.0, posinf=1.0, neginf=-1.0)


def _whiteness(blue: np.ndarray, green: np.ndarray, red: np.ndarray) -> np.ndarray:
    mean_visible = (blue + green + red) / 3.0
    deviation = (
        np.abs(blue - mean_visible)
        + np.abs(green - mean_visible)
        + np.abs(red - mean_visible)
    )
    return deviation / (mean_visible * 3.0 + EPSILON)


def _cloud_components(reflectance: list[np.ndarray]) -> tuple[np.ndarray, ...]:
    blue, green, red, nir, swir1 = reflectance[:5]
    visible_brightness = (blue + green + red) / 3.0
    whiteness = _whiteness(blue, green, red)
    ndvi = _normalized_difference(nir, red)
    ndsi = _normalized_difference(green, swir1)
    hot = blue - 0.5 * red - 0.08
    return blue, visible_brightness, whiteness, ndvi, ndsi, hot


def _cloud_score_from_components(
    blue: np.ndarray,
    visible_brightness: np.ndarray,
    whiteness: np.ndarray,
    ndvi: np.ndarray,
    ndsi: np.ndarray,
    hot: np.ndarray,
    params: CloudParams,
) -> np.ndarray:
    score = np.zeros_like(blue, dtype="float32")
    score += np.clip((visible_brightness - 0.15) / 0.55, 0, 1) * 0.30
    score += np.clip((blue - 0.12) / 0.50, 0, 1) * 0.20
    score += np.clip((params.whiteness_max - whiteness) / params.whiteness_max, 0, 1) * 0.20
    score += np.clip((params.ndvi_max - ndvi) / (params.ndvi_max + 1.0), 0, 1) * 0.15
    score += np.clip((params.ndsi_max - ndsi) / (params.ndsi_max + 1.0), 0, 1) * 0.10
    score += np.clip((hot - params.hot_threshold + 0.15) / 0.40, 0, 1) * 0.05
    np.clip(score, 0.0, 1.0, out=score)
    return score


def _clean_mask(mask: np.ndarray, params: CloudParams) -> np.ndarray:
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


def threshold_cloud(
    bands: List[np.ndarray],
    threshold: float | None = None,
    params: CloudParams | None = None,
) -> np.ndarray:
    params = params or CloudParams()
    reflectance = _as_reflectance_bands(bands, limit=min(len(bands), 2))
    blue = reflectance[0]

    mask = blue > params.blue_threshold

    if len(reflectance) >= 2:
        swir = reflectance[1]
        swir_threshold = params.swir_threshold if threshold is None else threshold
        mask = mask & (swir > swir_threshold)

    return _clean_mask(mask, params).astype("uint8")


def compute_cloud_score(
    bands: List[np.ndarray],
    params: CloudParams | None = None,
) -> np.ndarray:
    params = params or CloudParams()
    reflectance = _as_reflectance_bands(bands, limit=min(len(bands), 5))

    if len(reflectance) < 5:
        blue = reflectance[0]
        swir = reflectance[1] if len(reflectance) >= 2 else blue
        score = 0.65 * blue + 0.35 * swir
        np.clip(score, 0.0, 1.0, out=score)
        return score

    return _cloud_score_from_components(*_cloud_components(reflectance), params=params)


def fmask_cloud(
    bands: List[np.ndarray],
    threshold: float | None = None,
    params: CloudParams | None = None,
) -> np.ndarray:
    params = params or CloudParams()
    reflectance = _as_reflectance_bands(bands, limit=5)

    if len(reflectance) < 5:
        raise ValueError(
            "Fmask-like cloud extraction requires Blue, Green, Red, NIR, and SWIR1 bands"
        )

    blue, visible_brightness, whiteness, ndvi, ndsi, hot = _cloud_components(reflectance)

    cutoff = params.score_threshold if threshold is None else threshold
    score = _cloud_score_from_components(
        blue, visible_brightness, whiteness, ndvi, ndsi, hot, params
    )

    mask = (
        (score > cutoff)
        & (blue > params.blue_threshold)
        & (visible_brightness > params.brightness_threshold)
        & (whiteness < params.whiteness_max)
        & (ndvi < params.ndvi_max)
        & (ndsi < params.ndsi_max)
        & (hot > params.hot_threshold)
    )

    return _clean_mask(mask, params).astype("uint8")


def cirrus_cloud(
    bands: List[np.ndarray],
    threshold: float | None = None,
    params: CloudParams | None = None,
) -> np.ndarray:
    params = params or CloudParams(apply_morphology=False, min_component_size=1)
    reflectance = _as_reflectance_bands(bands, limit=1)
    cirrus = reflectance[0]
    cutoff = 0.01 if threshold is None else threshold
    return _clean_mask(cirrus > cutoff, params).astype("uint8")


def cloud_score_mask(
    bands: List[np.ndarray],
    threshold: float | None = None,
    params: CloudParams | None = None,
) -> np.ndarray:
    params = params or CloudParams()
    cutoff = params.score_threshold if threshold is None else threshold
    score = compute_cloud_score(bands, params)
    return _clean_mask(score > cutoff, params).astype("uint8")
