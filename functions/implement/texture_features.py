from __future__ import annotations

import math
import os
from typing import Any, Literal

import numpy as np
import rasterio
from numpy.lib.stride_tricks import sliding_window_view
from scipy import ndimage


TextureType = Literal["glcm", "local_statistics", "gabor", "lbp"]
GLCMProperty = Literal[
    "contrast",
    "dissimilarity",
    "homogeneity",
    "asm",
    "energy",
    "entropy",
    "correlation",
]
LocalStatistic = Literal["mean", "std", "variance", "range", "entropy"]

TEXTURE_TYPES = {"glcm", "local_statistics", "gabor", "lbp"}
GLCM_PROPERTIES = {
    "contrast",
    "dissimilarity",
    "homogeneity",
    "asm",
    "energy",
    "entropy",
    "correlation",
}
LOCAL_STATISTICS = {"mean", "std", "variance", "range", "entropy"}

_FLOAT_NODATA = -9999.0


def texture_feature_analysis(
    input_path: str,
    output_path: str,
    texture_type: str,
    band_index: int = 1,
    gray_levels: int = 32,
    window_size: int = 7,
    glcm_distance: int = 1,
    glcm_angle: float = 0.0,
    glcm_property: str = "contrast",
    local_stat: str = "mean",
    gabor_frequency: float = 0.2,
    gabor_theta: float = 0.0,
    gabor_sigma: float = 2.0,
    lbp_radius: float = 1.0,
    lbp_points: int = 8,
) -> dict[str, Any]:
    """Create a texture-derived raster product from a single image band."""

    feature_type = _normalize_texture_type(texture_type)
    if band_index < 1:
        raise ValueError("band_index must be greater than zero")

    with rasterio.open(input_path) as src:
        if band_index > src.count:
            raise ValueError(f"Raster has {src.count} bands; band_index {band_index} is out of range")
        band, valid_mask = _read_band(src, band_index)
        profile = src.profile.copy()

    if feature_type == "glcm":
        result, meta = _glcm_texture(
            band,
            valid_mask,
            gray_levels=gray_levels,
            window_size=window_size,
            distance=glcm_distance,
            angle=glcm_angle,
            property_name=glcm_property,
        )
        description = f"GLCM {meta['glcm_property']}"
    elif feature_type == "local_statistics":
        result, meta = _local_statistics(
            band,
            valid_mask,
            gray_levels=gray_levels,
            window_size=window_size,
            statistic=local_stat,
        )
        description = f"Local {meta['local_stat']}"
    elif feature_type == "gabor":
        result, meta = _gabor_filter(
            band,
            valid_mask,
            frequency=gabor_frequency,
            theta=gabor_theta,
            sigma=gabor_sigma,
        )
        description = "Gabor magnitude response"
    elif feature_type == "lbp":
        result, meta = _lbp(
            band,
            valid_mask,
            radius=lbp_radius,
            points=lbp_points,
        )
        description = "Local binary pattern code"
    else:
        raise ValueError(f"Unsupported texture_type: {texture_type}")

    output = _prepare_float_output(result, valid_mask)
    _write_single_band(output_path, profile, output, description, feature_type)

    return {
        "operation": "texture_feature_analysis",
        "texture_type": feature_type,
        "band_index": int(band_index),
        "width": int(output.shape[1]),
        "height": int(output.shape[0]),
        "dtype": "float32",
        "nodata": _FLOAT_NODATA,
        **meta,
    }


def _normalize_texture_type(texture_type: str) -> TextureType:
    value = str(texture_type or "").strip().lower().replace("-", "_")
    aliases = {
        "gray_level_cooccurrence_matrix": "glcm",
        "gray_level_co_occurrence_matrix": "glcm",
        "cooccurrence": "glcm",
        "co_occurrence": "glcm",
        "local_stats": "local_statistics",
        "local_stat": "local_statistics",
        "statistics_window": "local_statistics",
        "local_statistics_window": "local_statistics",
        "gabor_filter": "gabor",
        "gabor_filtering": "gabor",
        "local_binary_patterns": "lbp",
        "local_binary_pattern": "lbp",
    }
    value = aliases.get(value, value)
    if value not in TEXTURE_TYPES:
        available = ", ".join(sorted(TEXTURE_TYPES))
        raise ValueError(f"Unsupported texture_type '{texture_type}'. Available: {available}")
    return value  # type: ignore[return-value]


def _normalize_glcm_property(property_name: str) -> GLCMProperty:
    value = str(property_name or "contrast").strip().lower().replace("-", "_")
    if value in {"angular_second_moment", "second_moment"}:
        value = "asm"
    if value not in GLCM_PROPERTIES:
        available = ", ".join(sorted(GLCM_PROPERTIES))
        raise ValueError(f"glcm_property must be one of: {available}")
    return value  # type: ignore[return-value]


def _normalize_local_stat(statistic: str) -> LocalStatistic:
    value = str(statistic or "mean").strip().lower().replace("-", "_")
    if value in {"stdev", "standard_deviation"}:
        value = "std"
    if value in {"var"}:
        value = "variance"
    if value not in LOCAL_STATISTICS:
        available = ", ".join(sorted(LOCAL_STATISTICS))
        raise ValueError(f"local_stat must be one of: {available}")
    return value  # type: ignore[return-value]


def _read_band(src: rasterio.DatasetReader, band_index: int) -> tuple[np.ndarray, np.ndarray]:
    data = src.read(band_index, masked=True).astype("float32")
    band = np.asarray(data.filled(np.nan), dtype="float32")
    valid_mask = ~np.ma.getmaskarray(data) & np.isfinite(band)
    if not np.any(valid_mask):
        raise ValueError("Selected band has no valid pixels")
    return band, valid_mask


def _normalize_gray_levels(gray_levels: int) -> int:
    try:
        levels = int(gray_levels)
    except (TypeError, ValueError) as exc:
        raise ValueError("gray_levels must be an integer") from exc
    if levels < 2 or levels > 256:
        raise ValueError("gray_levels must be in the range [2, 256]")
    return levels


def _normalize_window_size(window_size: int) -> int:
    try:
        size = int(window_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("window_size must be an integer") from exc
    if size < 3:
        raise ValueError("window_size must be at least 3")
    if size % 2 == 0:
        size += 1
    return size


def _quantize(data: np.ndarray, valid_mask: np.ndarray, gray_levels: int) -> np.ndarray:
    levels = _normalize_gray_levels(gray_levels)
    values = data[valid_mask]
    value_min = float(np.nanmin(values))
    value_max = float(np.nanmax(values))
    quantized = np.zeros(data.shape, dtype=np.uint16)
    if not math.isfinite(value_min) or not math.isfinite(value_max):
        raise ValueError("Selected band has no finite pixels")
    if abs(value_max - value_min) <= 1e-12:
        return quantized

    scaled = (data[valid_mask] - value_min) / (value_max - value_min)
    quantized_values = np.floor(scaled * levels).astype(np.int32)
    quantized[valid_mask] = np.clip(quantized_values, 0, levels - 1).astype(np.uint16)
    return quantized


def _offset_from_angle(distance: int, angle_degrees: float) -> tuple[int, int]:
    try:
        dist = int(distance)
    except (TypeError, ValueError) as exc:
        raise ValueError("glcm_distance must be an integer") from exc
    if dist < 1:
        raise ValueError("glcm_distance must be at least 1")

    angle = math.radians(float(angle_degrees))
    row_offset = int(round(-math.sin(angle) * dist))
    col_offset = int(round(math.cos(angle) * dist))
    if row_offset == 0 and col_offset == 0:
        col_offset = dist
    return row_offset, col_offset


def _directional_pair_windows(
    quantized: np.ndarray,
    valid_mask: np.ndarray,
    window_size: int,
    row_offset: int,
    col_offset: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if abs(row_offset) >= window_size or abs(col_offset) >= window_size:
        raise ValueError("glcm_distance must be smaller than window_size")

    pad = window_size // 2
    padded_quantized = np.pad(quantized, pad, mode="edge")
    padded_valid = np.pad(valid_mask, pad, mode="constant", constant_values=False)
    value_windows = sliding_window_view(padded_quantized, (window_size, window_size))
    valid_windows = sliding_window_view(padded_valid, (window_size, window_size))

    src_rows = slice(max(0, -row_offset), window_size - max(0, row_offset))
    dst_rows = slice(max(0, row_offset), window_size - max(0, -row_offset))
    src_cols = slice(max(0, -col_offset), window_size - max(0, col_offset))
    dst_cols = slice(max(0, col_offset), window_size - max(0, -col_offset))

    source = value_windows[..., src_rows, src_cols]
    target = value_windows[..., dst_rows, dst_cols]
    pair_mask = valid_windows[..., src_rows, src_cols] & valid_windows[..., dst_rows, dst_cols]
    return source, target, pair_mask


def _glcm_texture(
    data: np.ndarray,
    valid_mask: np.ndarray,
    gray_levels: int,
    window_size: int,
    distance: int,
    angle: float,
    property_name: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    levels = _normalize_gray_levels(gray_levels)
    size = _normalize_window_size(window_size)
    selected_property = _normalize_glcm_property(property_name)
    row_offset, col_offset = _offset_from_angle(distance, angle)
    quantized = _quantize(data, valid_mask, levels)
    source, target, pair_mask = _directional_pair_windows(
        quantized,
        valid_mask,
        size,
        row_offset,
        col_offset,
    )

    count = pair_mask.sum(axis=(-2, -1)).astype("float64")
    result = np.full(data.shape, np.nan, dtype="float32")
    output_mask = valid_mask & (count > 0)

    if selected_property in {"asm", "energy", "entropy"}:
        codes = (source.astype(np.int32) * levels + target.astype(np.int32)).reshape(data.size, -1)
        masks = pair_mask.reshape(data.size, -1)
        result = _histogram_glcm_property(codes, masks, count.ravel(), levels, selected_property).reshape(data.shape)
    else:
        source_float = source.astype("float64")
        target_float = target.astype("float64")
        diff = source_float - target_float
        if selected_property == "contrast":
            values = np.where(pair_mask, diff * diff, 0.0).sum(axis=(-2, -1))
            result = _safe_divide(values, count)
        elif selected_property == "dissimilarity":
            values = np.where(pair_mask, np.abs(diff), 0.0).sum(axis=(-2, -1))
            result = _safe_divide(values, count)
        elif selected_property == "homogeneity":
            values = np.where(pair_mask, 1.0 / (1.0 + diff * diff), 0.0).sum(axis=(-2, -1))
            result = _safe_divide(values, count)
        elif selected_property == "correlation":
            masked_source = np.where(pair_mask, source_float, 0.0)
            masked_target = np.where(pair_mask, target_float, 0.0)
            mean_source = _safe_divide(masked_source.sum(axis=(-2, -1)), count)
            mean_target = _safe_divide(masked_target.sum(axis=(-2, -1)), count)
            source_sq = np.where(pair_mask, source_float * source_float, 0.0).sum(axis=(-2, -1))
            target_sq = np.where(pair_mask, target_float * target_float, 0.0).sum(axis=(-2, -1))
            source_target = np.where(pair_mask, source_float * target_float, 0.0).sum(axis=(-2, -1))
            var_source = np.maximum(_safe_divide(source_sq, count) - mean_source * mean_source, 0.0)
            var_target = np.maximum(_safe_divide(target_sq, count) - mean_target * mean_target, 0.0)
            covariance = _safe_divide(source_target, count) - mean_source * mean_target
            denominator = np.sqrt(var_source * var_target)
            result = np.divide(
                covariance,
                denominator,
                out=np.zeros_like(covariance, dtype="float64"),
                where=denominator > 1e-12,
            ).astype("float32")

    result = np.asarray(result, dtype="float32")
    result[~output_mask] = np.nan
    return result, {
        "gray_levels": int(levels),
        "window_size": int(size),
        "glcm_distance": int(distance),
        "glcm_angle": float(angle),
        "glcm_property": selected_property,
        "glcm_offset": {"row": int(row_offset), "col": int(col_offset)},
    }


def _histogram_glcm_property(
    codes: np.ndarray,
    masks: np.ndarray,
    counts: np.ndarray,
    gray_levels: int,
    property_name: GLCMProperty,
) -> np.ndarray:
    output = np.full(counts.shape, np.nan, dtype="float32")
    bins = gray_levels * gray_levels
    for index in np.flatnonzero(counts > 0):
        values = codes[index, masks[index]]
        histogram = np.bincount(values, minlength=bins).astype("float64")
        probabilities = histogram[histogram > 0] / counts[index]
        if property_name == "entropy":
            output[index] = float(-np.sum(probabilities * np.log(probabilities)))
        else:
            asm = float(np.sum(probabilities * probabilities))
            output[index] = math.sqrt(asm) if property_name == "energy" else asm
    return output


def _local_statistics(
    data: np.ndarray,
    valid_mask: np.ndarray,
    gray_levels: int,
    window_size: int,
    statistic: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    levels = _normalize_gray_levels(gray_levels)
    size = _normalize_window_size(window_size)
    selected_stat = _normalize_local_stat(statistic)

    if selected_stat == "entropy":
        result = _local_entropy(data, valid_mask, levels, size)
        return result, {"gray_levels": int(levels), "window_size": int(size), "local_stat": selected_stat}

    kernel = np.ones((size, size), dtype="float32")
    valid_float = valid_mask.astype("float32")
    counts = ndimage.convolve(valid_float, kernel, mode="constant", cval=0.0)
    filled = np.where(valid_mask, data, 0.0).astype("float32")
    sums = ndimage.convolve(filled, kernel, mode="constant", cval=0.0)
    mean = _safe_divide(sums, counts)

    if selected_stat == "mean":
        result = mean
    elif selected_stat in {"variance", "std"}:
        sum_squares = ndimage.convolve(filled * filled, kernel, mode="constant", cval=0.0)
        variance = np.maximum(_safe_divide(sum_squares, counts) - mean * mean, 0.0)
        result = np.sqrt(variance) if selected_stat == "std" else variance
    elif selected_stat == "range":
        high_input = np.where(valid_mask, data, -np.inf)
        low_input = np.where(valid_mask, data, np.inf)
        local_max = ndimage.maximum_filter(high_input, size=size, mode="constant", cval=-np.inf)
        local_min = ndimage.minimum_filter(low_input, size=size, mode="constant", cval=np.inf)
        result = local_max - local_min
    else:
        raise ValueError(f"Unsupported local_stat: {statistic}")

    result = np.asarray(result, dtype="float32")
    result[~valid_mask | (counts <= 0) | ~np.isfinite(result)] = np.nan
    return result, {"gray_levels": int(levels), "window_size": int(size), "local_stat": selected_stat}


def _local_entropy(
    data: np.ndarray,
    valid_mask: np.ndarray,
    gray_levels: int,
    window_size: int,
) -> np.ndarray:
    quantized = _quantize(data, valid_mask, gray_levels)
    pad = window_size // 2
    padded_quantized = np.pad(quantized, pad, mode="edge")
    padded_valid = np.pad(valid_mask, pad, mode="constant", constant_values=False)
    value_windows = sliding_window_view(padded_quantized, (window_size, window_size))
    valid_windows = sliding_window_view(padded_valid, (window_size, window_size))
    counts = valid_windows.sum(axis=(-2, -1)).astype("float64")
    entropy = np.zeros(data.shape, dtype="float64")
    for level in range(gray_levels):
        level_counts = ((value_windows == level) & valid_windows).sum(axis=(-2, -1)).astype("float64")
        probabilities = _safe_divide(level_counts, counts)
        positive = probabilities > 0.0
        entropy -= np.where(positive, probabilities * np.log(np.where(positive, probabilities, 1.0)), 0.0)
    entropy[~valid_mask | (counts <= 0) | ~np.isfinite(entropy)] = np.nan
    return entropy.astype("float32")


def _gabor_filter(
    data: np.ndarray,
    valid_mask: np.ndarray,
    frequency: float,
    theta: float,
    sigma: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    freq = float(frequency)
    angle = float(theta)
    sigma_value = float(sigma)
    if not math.isfinite(freq) or freq <= 0:
        raise ValueError("gabor_frequency must be greater than zero")
    if not math.isfinite(sigma_value) or sigma_value <= 0:
        raise ValueError("gabor_sigma must be greater than zero")

    real_kernel, imag_kernel = _gabor_kernels(freq, angle, sigma_value)
    filled = _fill_invalid(data, valid_mask)
    real_response = ndimage.convolve(filled, real_kernel, mode="nearest")
    imag_response = ndimage.convolve(filled, imag_kernel, mode="nearest")
    response = np.sqrt(real_response * real_response + imag_response * imag_response).astype("float32")
    response[~valid_mask | ~np.isfinite(response)] = np.nan
    return response, {
        "gabor_frequency": float(freq),
        "gabor_theta": float(angle),
        "gabor_sigma": float(sigma_value),
        "gabor_kernel_size": int(real_kernel.shape[0]),
    }


def _gabor_kernels(frequency: float, theta_degrees: float, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    radius = max(1, int(math.ceil(sigma * 3.0)))
    coords = np.arange(-radius, radius + 1, dtype="float64")
    y, x = np.meshgrid(coords, coords, indexing="ij")
    theta = math.radians(theta_degrees)
    x_theta = x * math.cos(theta) + y * math.sin(theta)
    y_theta = -x * math.sin(theta) + y * math.cos(theta)
    envelope = np.exp(-(x_theta * x_theta + y_theta * y_theta) / (2.0 * sigma * sigma))
    phase = 2.0 * math.pi * frequency * x_theta
    real_kernel = envelope * np.cos(phase)
    imag_kernel = envelope * np.sin(phase)
    real_kernel -= real_kernel.mean()
    real_norm = np.sum(np.abs(real_kernel))
    imag_norm = np.sum(np.abs(imag_kernel))
    if real_norm > 0:
        real_kernel /= real_norm
    if imag_norm > 0:
        imag_kernel /= imag_norm
    return real_kernel.astype("float32"), imag_kernel.astype("float32")


def _lbp(
    data: np.ndarray,
    valid_mask: np.ndarray,
    radius: float,
    points: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    radius_value = float(radius)
    try:
        point_count = int(points)
    except (TypeError, ValueError) as exc:
        raise ValueError("lbp_points must be an integer") from exc
    if not math.isfinite(radius_value) or radius_value <= 0:
        raise ValueError("lbp_radius must be greater than zero")
    if point_count < 1 or point_count > 24:
        raise ValueError("lbp_points must be in the range [1, 24]")

    rows, cols = np.indices(data.shape, dtype="float32")
    filled = _fill_invalid(data, valid_mask)
    valid_float = valid_mask.astype("float32")
    codes = np.zeros(data.shape, dtype="float64")
    output_mask = valid_mask.copy()

    for point in range(point_count):
        angle = 2.0 * math.pi * point / point_count
        sample_rows = rows - radius_value * math.sin(angle)
        sample_cols = cols + radius_value * math.cos(angle)
        sampled = ndimage.map_coordinates(
            filled,
            [sample_rows, sample_cols],
            order=1,
            mode="nearest",
        )
        sampled_valid = ndimage.map_coordinates(
            valid_float,
            [sample_rows, sample_cols],
            order=0,
            mode="nearest",
        ) > 0.5
        codes += np.where(sampled >= filled, 2.0**point, 0.0)
        output_mask &= sampled_valid

    codes[~output_mask | ~np.isfinite(codes)] = np.nan
    return codes.astype("float32"), {"lbp_radius": float(radius_value), "lbp_points": int(point_count)}


def _fill_invalid(data: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    filled = np.asarray(data, dtype="float32").copy()
    mean_value = float(np.nanmean(filled[valid_mask]))
    if not math.isfinite(mean_value):
        mean_value = 0.0
    filled[~valid_mask] = mean_value
    return filled


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype="float64"),
        where=denominator > 0,
    )


def _prepare_float_output(result: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    output = np.asarray(result, dtype="float32").copy()
    output[~valid_mask | ~np.isfinite(output)] = _FLOAT_NODATA
    return output


def _write_single_band(
    output_path: str,
    profile: dict[str, Any],
    data: np.ndarray,
    description: str,
    texture_type: str,
) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    profile.update(
        driver="GTiff",
        count=1,
        dtype="float32",
        nodata=_FLOAT_NODATA,
        compress="lzw",
    )
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data.astype("float32"), 1)
        dst.set_band_description(1, description)
        dst.update_tags(TEXTURE_FEATURE_ANALYSIS="true", TEXTURE_TYPE=texture_type)
