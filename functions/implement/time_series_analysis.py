from __future__ import annotations

import math
import os
import re
import warnings
from datetime import date, datetime
from typing import Any, Literal

import numpy as np
import rasterio
from scipy import signal


TimeSeriesOperation = Literal[
    "monthly_composite",
    "annual_composite",
    "maximum_composite",
    "median_composite",
    "moving_window_smoothing",
    "savitzky_golay",
    "trend",
    "seasonality",
    "phenology",
]

TIME_SERIES_OPERATIONS = {
    "monthly_composite",
    "annual_composite",
    "maximum_composite",
    "median_composite",
    "moving_window_smoothing",
    "savitzky_golay",
    "trend",
    "seasonality",
    "phenology",
}

_FLOAT_NODATA = -9999.0


def time_series_analysis(
    input_paths: list[str],
    output_path: str,
    operation: str,
    band_index: int = 1,
    dates: list[str] | str | None = None,
    moving_window_size: int = 3,
    savgol_window_length: int = 5,
    savgol_polyorder: int = 2,
    phenology_threshold_ratio: float = 0.2,
) -> dict[str, Any]:
    """Create compositing, smoothing, trend, seasonality, or phenology products."""

    operation_name = _normalize_operation(operation)
    if not input_paths:
        raise ValueError("At least one input raster is required")
    if band_index < 1:
        raise ValueError("band_index must be greater than zero")

    stack, valid_mask, profile = _read_time_stack(input_paths, band_index)
    parsed_dates = _parse_dates(dates, len(input_paths))
    if parsed_dates is not None:
        order = np.argsort(np.asarray([item.toordinal() for item in parsed_dates]))
        stack = stack[order]
        valid_mask = valid_mask[order]
        parsed_dates = [parsed_dates[int(index)] for index in order]

    if operation_name == "monthly_composite":
        _require_dates(parsed_dates, operation_name)
        output, descriptions, meta = _grouped_composite(
            stack,
            valid_mask,
            _month_labels(parsed_dates or []),
            statistic="mean",
        )
    elif operation_name == "annual_composite":
        _require_dates(parsed_dates, operation_name)
        output, descriptions, meta = _grouped_composite(
            stack,
            valid_mask,
            _year_labels(parsed_dates or []),
            statistic="mean",
        )
    elif operation_name == "maximum_composite":
        output = _single_composite(stack, valid_mask, "max")
        descriptions = ["Maximum value composite"]
        meta = {"composite_statistic": "max"}
    elif operation_name == "median_composite":
        output = _single_composite(stack, valid_mask, "median")
        descriptions = ["Median composite"]
        meta = {"composite_statistic": "median"}
    elif operation_name == "moving_window_smoothing":
        output = _moving_window_smoothing(stack, valid_mask, moving_window_size)
        descriptions = _time_descriptions("Moving window smooth", output.shape[0], parsed_dates)
        meta = {"moving_window_size": _normalize_odd_window(moving_window_size, minimum=1)}
    elif operation_name == "savitzky_golay":
        output, meta = _savitzky_golay(stack, valid_mask, savgol_window_length, savgol_polyorder)
        descriptions = _time_descriptions("Savitzky-Golay smooth", output.shape[0], parsed_dates)
    elif operation_name == "trend":
        output, meta = _trend(stack, valid_mask, parsed_dates)
        descriptions = ["Trend slope", "Trend intercept", "Trend R2"]
    elif operation_name == "seasonality":
        output, meta = _seasonality(stack, valid_mask, parsed_dates)
        descriptions = ["Seasonal mean", "Seasonal amplitude", "Peak timing", "Trough timing"]
    elif operation_name == "phenology":
        output, meta = _phenology(stack, valid_mask, parsed_dates, phenology_threshold_ratio)
        descriptions = [
            "Start of season",
            "End of season",
            "Peak of season",
            "Season length",
            "Seasonal amplitude",
        ]
    else:
        raise ValueError(f"Unsupported time-series operation: {operation}")

    output = _prepare_float_stack(output)
    _write_stack(output_path, profile, output, descriptions, operation_name)
    return {
        "operation": "time_series_analysis",
        "time_series_operation": operation_name,
        "band_index": int(band_index),
        "input_count": int(stack.shape[0]),
        "width": int(output.shape[2]),
        "height": int(output.shape[1]),
        "bands": int(output.shape[0]),
        "dates": [item.isoformat() for item in parsed_dates] if parsed_dates else None,
        **meta,
    }


def _normalize_operation(operation: str) -> TimeSeriesOperation:
    value = str(operation or "").strip().lower().replace("-", "_")
    aliases = {
        "monthly": "monthly_composite",
        "monthly_compositing": "monthly_composite",
        "annual": "annual_composite",
        "annual_compositing": "annual_composite",
        "max": "maximum_composite",
        "maximum": "maximum_composite",
        "maximum_value_composite": "maximum_composite",
        "maximum_value_compositing": "maximum_composite",
        "median": "median_composite",
        "median_compositing": "median_composite",
        "moving_average": "moving_window_smoothing",
        "moving_window": "moving_window_smoothing",
        "smooth": "moving_window_smoothing",
        "savgol": "savitzky_golay",
        "savitzky_golay_filtering": "savitzky_golay",
        "savitzky_golay_filter": "savitzky_golay",
        "trend_analysis": "trend",
        "seasonality_analysis": "seasonality",
        "phenological_parameter_extraction": "phenology",
        "phenological_parameters": "phenology",
        "phenology_extraction": "phenology",
    }
    value = aliases.get(value, value)
    if value not in TIME_SERIES_OPERATIONS:
        available = ", ".join(sorted(TIME_SERIES_OPERATIONS))
        raise ValueError(f"Unsupported time-series operation '{operation}'. Available: {available}")
    return value  # type: ignore[return-value]


def _read_time_stack(
    input_paths: list[str],
    band_index: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    arrays: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    profile: dict[str, Any] | None = None
    reference_shape: tuple[int, int] | None = None
    reference_transform = None
    reference_crs = None

    for path in input_paths:
        with rasterio.open(path) as src:
            if band_index > src.count:
                raise ValueError(f"Raster {path} has {src.count} bands; band_index {band_index} is out of range")

            if profile is None:
                profile = src.profile.copy()
                reference_shape = (src.height, src.width)
                reference_transform = src.transform
                reference_crs = src.crs
            elif (
                (src.height, src.width) != reference_shape
                or src.transform != reference_transform
                or src.crs != reference_crs
            ):
                raise ValueError("All time-series rasters must share dimensions, transform, and CRS")

            data = src.read(band_index, masked=True).astype("float32")
            band = np.asarray(data.filled(np.nan), dtype="float32")
            valid = ~np.ma.getmaskarray(data) & np.isfinite(band)
            arrays.append(band)
            masks.append(valid)

    stack = np.stack(arrays, axis=0)
    valid_mask = np.stack(masks, axis=0)
    if not np.any(valid_mask):
        raise ValueError("The selected time series has no valid pixels")
    return stack, valid_mask, profile or {}


def _parse_dates(values: list[str] | str | None, expected_count: int) -> list[date] | None:
    if values is None:
        return None
    if isinstance(values, str):
        parts = [part.strip() for part in re.split(r"[\n,;]+", values) if part.strip()]
    else:
        parts = [str(item).strip() for item in values if str(item).strip()]
    if not parts:
        return None
    if len(parts) != expected_count:
        raise ValueError(f"dates must contain {expected_count} values")
    return [_parse_date(item) for item in parts]


def _parse_date(value: str) -> date:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m", "%Y/%m", "%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ValueError(f"Invalid date value: {value}") from exc


def _require_dates(values: list[date] | None, operation: str) -> None:
    if not values:
        raise ValueError(f"{operation} requires acquisition dates")


def _month_labels(values: list[date]) -> list[str]:
    return [f"{item.year:04d}-{item.month:02d}" for item in values]


def _year_labels(values: list[date]) -> list[str]:
    return [f"{item.year:04d}" for item in values]


def _grouped_composite(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    labels: list[str],
    statistic: str,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    unique_labels = list(dict.fromkeys(labels))
    bands = []
    descriptions = []
    for label in unique_labels:
        indices = [index for index, value in enumerate(labels) if value == label]
        bands.append(_single_composite(stack[indices], valid_mask[indices], statistic)[0])
        descriptions.append(f"{label} {statistic} composite")
    return np.stack(bands, axis=0), descriptions, {
        "composite_statistic": statistic,
        "groups": unique_labels,
    }


def _single_composite(stack: np.ndarray, valid_mask: np.ndarray, statistic: str) -> np.ndarray:
    masked = np.where(valid_mask, stack, np.nan)
    counts = valid_mask.sum(axis=0)
    if statistic == "mean":
        sums = np.where(valid_mask, stack, 0.0).sum(axis=0)
        result = np.divide(
            sums,
            counts,
            out=np.full(stack.shape[1:], np.nan, dtype="float64"),
            where=counts > 0,
        )
    elif statistic == "max":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            result = np.nanmax(masked, axis=0)
        result[counts == 0] = np.nan
    elif statistic == "median":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            result = np.nanmedian(masked, axis=0)
        result[counts == 0] = np.nan
    else:
        raise ValueError(f"Unsupported composite statistic: {statistic}")
    return result[np.newaxis, :, :].astype("float32")


def _normalize_odd_window(value: int, minimum: int = 3, maximum: int | None = None) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("window size must be an integer") from exc
    if size < minimum:
        size = minimum
    if maximum is not None:
        size = min(size, maximum)
    if size % 2 == 0:
        size += 1
        if maximum is not None and size > maximum:
            size -= 2
    return max(size, minimum)


def _moving_window_smoothing(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    window_size: int,
) -> np.ndarray:
    size = _normalize_odd_window(window_size, minimum=1)
    half = size // 2
    output = np.full(stack.shape, np.nan, dtype="float32")
    for index in range(stack.shape[0]):
        start = max(0, index - half)
        stop = min(stack.shape[0], index + half + 1)
        counts = valid_mask[start:stop].sum(axis=0)
        sums = np.where(valid_mask[start:stop], stack[start:stop], 0.0).sum(axis=0)
        output[index] = np.divide(
            sums,
            counts,
            out=np.full(stack.shape[1:], np.nan, dtype="float64"),
            where=counts > 0,
        ).astype("float32")
    return output


def _savitzky_golay(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    window_length: int,
    polyorder: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    if stack.shape[0] < 3:
        raise ValueError("Savitzky-Golay filtering requires at least three rasters")
    try:
        order = int(polyorder)
    except (TypeError, ValueError) as exc:
        raise ValueError("savgol_polyorder must be an integer") from exc
    if order < 0:
        raise ValueError("savgol_polyorder must be zero or greater")

    max_window = stack.shape[0] if stack.shape[0] % 2 == 1 else stack.shape[0] - 1
    size = _normalize_odd_window(window_length, minimum=3, maximum=max_window)
    if order >= size:
        raise ValueError("savgol_polyorder must be smaller than savgol_window_length")

    filled, valid_any = _interpolate_missing(stack, valid_mask)
    output = signal.savgol_filter(filled, window_length=size, polyorder=order, axis=0, mode="interp")
    output[:, ~valid_any] = np.nan
    return output.astype("float32"), {
        "savgol_window_length": int(size),
        "savgol_polyorder": int(order),
    }


def _interpolate_missing(stack: np.ndarray, valid_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    time_count, height, width = stack.shape
    series = stack.reshape(time_count, -1)
    valid = valid_mask.reshape(time_count, -1)
    filled = np.full_like(series, np.nan, dtype="float32")
    x = np.arange(time_count, dtype="float64")
    valid_any = valid.any(axis=0)

    for pixel in np.flatnonzero(valid_any):
        pixel_valid = valid[:, pixel]
        values = series[pixel_valid, pixel]
        if values.size == 1:
            filled[:, pixel] = values[0]
        else:
            filled[:, pixel] = np.interp(x, x[pixel_valid], values).astype("float32")

    return filled.reshape(stack.shape), valid_any.reshape(height, width)


def _time_axis(values: list[date] | None, count: int) -> np.ndarray:
    if not values:
        return np.arange(count, dtype="float64")
    start = values[0].toordinal()
    return np.asarray([item.toordinal() - start for item in values], dtype="float64")


def _trend(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    dates: list[date] | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    if stack.shape[0] < 2:
        raise ValueError("Trend analysis requires at least two rasters")

    x = _time_axis(dates, stack.shape[0])[:, np.newaxis, np.newaxis]
    y = np.where(valid_mask, stack, 0.0).astype("float64")
    valid = valid_mask.astype("float64")
    n = valid.sum(axis=0)
    sx = (x * valid).sum(axis=0)
    sy = y.sum(axis=0)
    sxx = (x * x * valid).sum(axis=0)
    syy = (y * y).sum(axis=0)
    sxy = (x * y).sum(axis=0)

    denominator = n * sxx - sx * sx
    slope = np.divide(
        n * sxy - sx * sy,
        denominator,
        out=np.full(stack.shape[1:], np.nan, dtype="float64"),
        where=(n >= 2) & (np.abs(denominator) > 1e-12),
    )
    intercept = np.divide(
        sy - slope * sx,
        n,
        out=np.full(stack.shape[1:], np.nan, dtype="float64"),
        where=n > 0,
    )

    corr_num = n * sxy - sx * sy
    corr_den = (n * sxx - sx * sx) * (n * syy - sy * sy)
    r2 = np.divide(
        corr_num * corr_num,
        corr_den,
        out=np.full(stack.shape[1:], np.nan, dtype="float64"),
        where=(n >= 2) & (corr_den > 1e-12),
    )
    output = np.stack([slope, intercept, np.clip(r2, 0.0, 1.0)], axis=0)
    return output.astype("float32"), {"trend_time_unit": "days" if dates else "time_step"}


def _timing_values(values: list[date] | None, count: int) -> np.ndarray:
    if values:
        return np.asarray([item.timetuple().tm_yday for item in values], dtype="float32")
    return np.arange(1, count + 1, dtype="float32")


def _seasonality(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    dates: list[date] | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    counts = valid_mask.sum(axis=0)
    sums = np.where(valid_mask, stack, 0.0).sum(axis=0)
    mean = np.divide(
        sums,
        counts,
        out=np.full(stack.shape[1:], np.nan, dtype="float64"),
        where=counts > 0,
    )
    high_input = np.where(valid_mask, stack, -np.inf)
    low_input = np.where(valid_mask, stack, np.inf)
    max_value = high_input.max(axis=0)
    min_value = low_input.min(axis=0)
    amplitude = max_value - min_value
    peak_index = np.argmax(high_input, axis=0)
    trough_index = np.argmin(low_input, axis=0)
    timing = _timing_values(dates, stack.shape[0])
    peak_timing = timing[peak_index]
    trough_timing = timing[trough_index]

    no_data = counts == 0
    for arr in (mean, amplitude, peak_timing, trough_timing):
        arr[no_data] = np.nan
    output = np.stack([mean, amplitude, peak_timing, trough_timing], axis=0)
    return output.astype("float32"), {"timing_unit": "day_of_year" if dates else "time_step"}


def _phenology(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    dates: list[date] | None,
    threshold_ratio: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    ratio = float(threshold_ratio)
    if not math.isfinite(ratio) or ratio < 0 or ratio > 1:
        raise ValueError("phenology_threshold_ratio must be in the range [0, 1]")

    filled, valid_any = _interpolate_missing(stack, valid_mask)
    smoothed = filled
    time_count, height, width = smoothed.shape
    series = smoothed.reshape(time_count, -1)
    valid_pixels = valid_any.ravel()
    timing = _timing_values(dates, time_count)
    elapsed = _time_axis(dates, time_count).astype("float32") if dates else np.arange(time_count, dtype="float32")

    output = np.full((5, series.shape[1]), np.nan, dtype="float32")
    for pixel in np.flatnonzero(valid_pixels):
        values = series[:, pixel]
        if not np.all(np.isfinite(values)):
            continue
        min_value = float(values.min())
        max_value = float(values.max())
        amplitude = max_value - min_value
        if amplitude <= 1e-12:
            continue
        peak_index = int(np.argmax(values))
        threshold = min_value + ratio * amplitude

        above = values >= threshold
        start_candidates = np.flatnonzero(above[: peak_index + 1])
        end_candidates = np.flatnonzero(above[peak_index:])
        if start_candidates.size == 0 or end_candidates.size == 0:
            continue

        start_index = int(start_candidates[0])
        end_index = int(peak_index + end_candidates[-1])
        output[:, pixel] = [
            timing[start_index],
            timing[end_index],
            timing[peak_index],
            elapsed[end_index] - elapsed[start_index],
            amplitude,
        ]

    return output.reshape(5, height, width), {
        "phenology_threshold_ratio": float(ratio),
        "timing_unit": "day_of_year" if dates else "time_step",
    }


def _time_descriptions(prefix: str, count: int, dates: list[date] | None) -> list[str]:
    if dates:
        return [f"{prefix} {item.isoformat()}" for item in dates]
    return [f"{prefix} T{index + 1}" for index in range(count)]


def _prepare_float_stack(stack: np.ndarray) -> np.ndarray:
    output = np.asarray(stack, dtype="float32").copy()
    output[~np.isfinite(output)] = _FLOAT_NODATA
    return output


def _write_stack(
    output_path: str,
    profile: dict[str, Any],
    stack: np.ndarray,
    descriptions: list[str],
    operation: str,
) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    profile.update(
        driver="GTiff",
        count=int(stack.shape[0]),
        dtype="float32",
        nodata=_FLOAT_NODATA,
        compress="lzw",
    )
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(stack.astype("float32"))
        for band_index, description in enumerate(descriptions, start=1):
            dst.set_band_description(band_index, description)
        dst.update_tags(TIME_SERIES_ANALYSIS="true", TIME_SERIES_OPERATION=operation)
