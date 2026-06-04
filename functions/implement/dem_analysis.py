from __future__ import annotations

import math
import os
from collections import deque
from typing import Any, Literal

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS
from scipy import ndimage


DEMOperation = Literal[
    "elevation",
    "slope",
    "aspect",
    "hillshade",
    "curvature",
    "relief",
    "twi",
    "flow_direction",
    "flow_accumulation",
    "watershed",
]


DEM_OPERATIONS = {
    "elevation",
    "slope",
    "aspect",
    "hillshade",
    "curvature",
    "relief",
    "twi",
    "flow_direction",
    "flow_accumulation",
    "watershed",
}

_FLOAT_NODATA = -9999.0

_D8_OFFSETS = (
    (0, 1, 1, "east"),
    (1, 1, 2, "southeast"),
    (1, 0, 4, "south"),
    (1, -1, 8, "southwest"),
    (0, -1, 16, "west"),
    (-1, -1, 32, "northwest"),
    (-1, 0, 64, "north"),
    (-1, 1, 128, "northeast"),
)


def dem_analysis(
    input_path: str,
    output_path: str,
    operation: str,
    band_index: int = 1,
    z_factor: float = 1.0,
    slope_unit: str = "degrees",
    hillshade_azimuth: float = 315.0,
    hillshade_altitude: float = 45.0,
    relief_window_size: int = 3,
    min_slope_degrees: float = 0.1,
) -> dict[str, Any]:
    """Create a DEM-derived raster product from a single elevation band."""

    operation_name = _normalize_operation(operation)
    if band_index < 1:
        raise ValueError("band_index must be greater than zero")
    if not math.isfinite(float(z_factor)) or float(z_factor) <= 0:
        raise ValueError("z_factor must be greater than zero")

    with rasterio.open(input_path) as src:
        if band_index > src.count:
            raise ValueError(f"Raster has {src.count} bands; band_index {band_index} is out of range")

        dem, valid_mask = _read_dem(src, band_index)
        x_size, y_size, mean_cell_size = _cell_sizes(src)
        profile = src.profile.copy()

    scaled_dem = dem * float(z_factor)

    if operation_name == "elevation":
        result = dem.astype("float32")
        dtype = "float32"
        nodata = _FLOAT_NODATA
        description = "Elevation"
    elif operation_name == "slope":
        result = _slope(scaled_dem, valid_mask, x_size, y_size, slope_unit)
        dtype = "float32"
        nodata = _FLOAT_NODATA
        description = f"Slope ({_normalize_slope_unit(slope_unit)})"
    elif operation_name == "aspect":
        result = _aspect(scaled_dem, valid_mask, x_size, y_size)
        dtype = "float32"
        nodata = _FLOAT_NODATA
        description = "Aspect (degrees clockwise from north)"
    elif operation_name == "hillshade":
        result = _hillshade(
            scaled_dem,
            valid_mask,
            x_size,
            y_size,
            hillshade_azimuth,
            hillshade_altitude,
        )
        dtype = "float32"
        nodata = _FLOAT_NODATA
        description = "Hillshade"
    elif operation_name == "curvature":
        result = _curvature(scaled_dem, valid_mask, x_size, y_size)
        dtype = "float32"
        nodata = _FLOAT_NODATA
        description = "Curvature"
    elif operation_name == "relief":
        result = _relief(dem, valid_mask, relief_window_size)
        dtype = "float32"
        nodata = _FLOAT_NODATA
        description = f"Topographic relief ({_normalize_window_size(relief_window_size)} px window)"
    elif operation_name == "twi":
        _, receiver = _d8_flow(dem, valid_mask, x_size, y_size, float(z_factor))
        result = _twi(
            scaled_dem,
            valid_mask,
            receiver,
            x_size,
            y_size,
            mean_cell_size,
            min_slope_degrees,
        )
        dtype = "float32"
        nodata = _FLOAT_NODATA
        description = "Topographic humidity index"
    elif operation_name == "flow_direction":
        direction, _ = _d8_flow(dem, valid_mask, x_size, y_size, float(z_factor))
        result = direction
        dtype = "uint8"
        nodata = 0
        description = "D8 flow direction"
    elif operation_name == "flow_accumulation":
        _, receiver = _d8_flow(dem, valid_mask, x_size, y_size, float(z_factor))
        result = _flow_accumulation(receiver, valid_mask).astype("float32")
        dtype = "float32"
        nodata = _FLOAT_NODATA
        description = "D8 flow accumulation"
    elif operation_name == "watershed":
        _, receiver = _d8_flow(dem, valid_mask, x_size, y_size, float(z_factor))
        result = _watershed_labels(receiver, valid_mask)
        dtype = "int32"
        nodata = 0
        description = "D8 watershed basin labels"
    else:
        # _normalize_operation prevents this branch, but it keeps type checkers honest.
        raise ValueError(f"Unsupported DEM operation: {operation}")

    output_array = _prepare_output(result, valid_mask, dtype, nodata)
    _write_single_band(output_path, profile, output_array, dtype, nodata, description, operation_name)

    return {
        "operation": "dem_analysis",
        "dem_operation": operation_name,
        "band_index": int(band_index),
        "z_factor": float(z_factor),
        "width": int(output_array.shape[1]),
        "height": int(output_array.shape[0]),
        "dtype": dtype,
        "nodata": nodata,
        "cell_size": {
            "x": float(x_size),
            "y": float(y_size),
            "mean": float(mean_cell_size),
        },
        "flow_direction_encoding": _flow_direction_encoding() if operation_name in {"flow_direction", "flow_accumulation", "watershed", "twi"} else None,
    }


def _normalize_operation(operation: str) -> DEMOperation:
    value = str(operation or "").strip().lower().replace("-", "_")
    aliases = {
        "shade": "hillshade",
        "shading": "hillshade",
        "topographic_relief": "relief",
        "topographic_humidity_index": "twi",
        "topographic_wetness_index": "twi",
        "humidity_index": "twi",
        "wetness_index": "twi",
        "flowdir": "flow_direction",
        "flowacc": "flow_accumulation",
        "flow_acc": "flow_accumulation",
        "watershed_delineation": "watershed",
    }
    value = aliases.get(value, value)
    if value not in DEM_OPERATIONS:
        available = ", ".join(sorted(DEM_OPERATIONS))
        raise ValueError(f"Unsupported DEM operation '{operation}'. Available: {available}")
    return value  # type: ignore[return-value]


def _read_dem(src: rasterio.DatasetReader, band_index: int) -> tuple[np.ndarray, np.ndarray]:
    data = src.read(band_index, masked=True).astype("float32")
    dem = np.asarray(data.filled(np.nan), dtype="float32")
    valid_mask = ~np.ma.getmaskarray(data) & np.isfinite(dem)
    if not np.any(valid_mask):
        raise ValueError("Selected DEM band has no valid elevation pixels")
    return dem, valid_mask


def _cell_sizes(src: rasterio.DatasetReader) -> tuple[float, float, float]:
    x_pixel, y_pixel = _pixel_size_from_transform(src.transform)
    x_size = x_pixel
    y_size = y_pixel

    if src.crs:
        crs = CRS.from_user_input(src.crs)
        if crs.is_geographic:
            center_lat = (src.bounds.top + src.bounds.bottom) / 2.0
            meters_per_degree_lat = (
                111132.92
                - 559.82 * math.cos(math.radians(2 * center_lat))
                + 1.175 * math.cos(math.radians(4 * center_lat))
                - 0.0023 * math.cos(math.radians(6 * center_lat))
            )
            meters_per_degree_lon = (
                111412.84 * math.cos(math.radians(center_lat))
                - 93.5 * math.cos(math.radians(3 * center_lat))
                + 0.118 * math.cos(math.radians(5 * center_lat))
            )
            x_size = max(abs(x_pixel * meters_per_degree_lon), 1e-12)
            y_size = max(abs(y_pixel * meters_per_degree_lat), 1e-12)
        elif crs.is_projected:
            unit_factor = _linear_unit_factor(crs)
            x_size = max(abs(x_pixel * unit_factor), 1e-12)
            y_size = max(abs(y_pixel * unit_factor), 1e-12)

    x_size = max(abs(x_size), 1e-12)
    y_size = max(abs(y_size), 1e-12)
    return x_size, y_size, (x_size + y_size) / 2.0


def _pixel_size_from_transform(transform: Affine) -> tuple[float, float]:
    x_size = math.hypot(transform.a, transform.d)
    y_size = math.hypot(transform.b, transform.e)
    if x_size == 0:
        x_size = abs(transform.a) or 1.0
    if y_size == 0:
        y_size = abs(transform.e) or 1.0
    return x_size, y_size


def _linear_unit_factor(crs: CRS) -> float:
    axis_info = crs.axis_info or []
    if not axis_info:
        return 1.0
    try:
        return float(getattr(axis_info[0], "unit_conversion_factor", 1.0) or 1.0)
    except (TypeError, ValueError):
        return 1.0


def _gradient(dem: np.ndarray, x_size: float, y_size: float) -> tuple[np.ndarray, np.ndarray]:
    dz_drow, dz_dx = np.gradient(dem, y_size, x_size, edge_order=1)
    return dz_dx.astype("float32"), dz_drow.astype("float32")


def _slope_radians(dem: np.ndarray, valid_mask: np.ndarray, x_size: float, y_size: float) -> np.ndarray:
    dz_dx, dz_drow = _gradient(dem, x_size, y_size)
    radians = np.arctan(np.hypot(dz_dx, dz_drow))
    radians[~valid_mask | ~np.isfinite(radians)] = np.nan
    return radians.astype("float32")


def _slope(
    dem: np.ndarray,
    valid_mask: np.ndarray,
    x_size: float,
    y_size: float,
    unit: str,
) -> np.ndarray:
    radians = _slope_radians(dem, valid_mask, x_size, y_size)
    normalized_unit = _normalize_slope_unit(unit)
    if normalized_unit == "radians":
        return radians
    if normalized_unit == "percent":
        result = np.tan(radians) * 100.0
    else:
        result = np.degrees(radians)
    result[~valid_mask | ~np.isfinite(result)] = np.nan
    return result.astype("float32")


def _normalize_slope_unit(unit: str) -> str:
    value = str(unit or "degrees").strip().lower()
    if value in {"degree", "degrees", "deg"}:
        return "degrees"
    if value in {"percent", "percentage", "pct"}:
        return "percent"
    if value in {"radian", "radians", "rad"}:
        return "radians"
    raise ValueError("slope_unit must be degrees, percent, or radians")


def _aspect(dem: np.ndarray, valid_mask: np.ndarray, x_size: float, y_size: float) -> np.ndarray:
    dz_dx, dz_drow = _gradient(dem, x_size, y_size)
    aspect = (np.degrees(np.arctan2(-dz_dx, dz_drow)) + 360.0) % 360.0
    flat = np.hypot(dz_dx, dz_drow) <= 1e-12
    aspect[flat | ~valid_mask | ~np.isfinite(aspect)] = -1.0
    return aspect.astype("float32")


def _hillshade(
    dem: np.ndarray,
    valid_mask: np.ndarray,
    x_size: float,
    y_size: float,
    azimuth: float,
    altitude: float,
) -> np.ndarray:
    if altitude <= 0 or altitude > 90:
        raise ValueError("hillshade_altitude must be in the range (0, 90]")

    dz_dx, dz_drow = _gradient(dem, x_size, y_size)
    dz_dnorth = -dz_drow
    azimuth_rad = math.radians(float(azimuth) % 360.0)
    altitude_rad = math.radians(float(altitude))

    light_east = math.cos(altitude_rad) * math.sin(azimuth_rad)
    light_north = math.cos(altitude_rad) * math.cos(azimuth_rad)
    light_up = math.sin(altitude_rad)

    normal_east = -dz_dx
    normal_north = -dz_dnorth
    normal_up = np.ones_like(dem, dtype="float32")
    normal_length = np.sqrt(normal_east * normal_east + normal_north * normal_north + 1.0)
    shade = (
        normal_east * light_east
        + normal_north * light_north
        + normal_up * light_up
    ) / normal_length
    shade = np.clip(shade, 0.0, 1.0) * 255.0
    shade[~valid_mask | ~np.isfinite(shade)] = np.nan
    return shade.astype("float32")


def _curvature(dem: np.ndarray, valid_mask: np.ndarray, x_size: float, y_size: float) -> np.ndarray:
    dz_dx, dz_drow = _gradient(dem, x_size, y_size)
    _, d2z_dx2 = np.gradient(dz_dx, y_size, x_size, edge_order=1)
    d2z_drow2, _ = np.gradient(dz_drow, y_size, x_size, edge_order=1)
    curvature = d2z_dx2 + d2z_drow2
    curvature[~valid_mask | ~np.isfinite(curvature)] = np.nan
    return curvature.astype("float32")


def _relief(dem: np.ndarray, valid_mask: np.ndarray, window_size: int) -> np.ndarray:
    size = _normalize_window_size(window_size)
    high_input = np.where(valid_mask, dem, -np.inf)
    low_input = np.where(valid_mask, dem, np.inf)
    local_max = ndimage.maximum_filter(high_input, size=size, mode="nearest")
    local_min = ndimage.minimum_filter(low_input, size=size, mode="nearest")
    relief = local_max - local_min
    relief[~valid_mask | ~np.isfinite(relief)] = np.nan
    return relief.astype("float32")


def _normalize_window_size(window_size: int) -> int:
    try:
        size = int(window_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("relief_window_size must be an integer") from exc
    if size < 3:
        raise ValueError("relief_window_size must be at least 3")
    if size % 2 == 0:
        size += 1
    return size


def _twi(
    dem: np.ndarray,
    valid_mask: np.ndarray,
    receiver: np.ndarray,
    x_size: float,
    y_size: float,
    mean_cell_size: float,
    min_slope_degrees: float,
) -> np.ndarray:
    accumulation = _flow_accumulation(receiver, valid_mask).astype("float32")
    slope_rad = _slope_radians(dem, valid_mask, x_size, y_size)
    min_slope_rad = math.radians(max(float(min_slope_degrees), 1e-6))
    slope_rad = np.maximum(slope_rad, min_slope_rad)
    cell_area = x_size * y_size
    specific_catchment_area = np.maximum(accumulation * cell_area / mean_cell_size, mean_cell_size)
    twi = np.log(specific_catchment_area / np.tan(slope_rad))
    twi[~valid_mask | ~np.isfinite(twi)] = np.nan
    return twi.astype("float32")


def _d8_flow(
    dem: np.ndarray,
    valid_mask: np.ndarray,
    x_size: float,
    y_size: float,
    z_factor: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = dem.shape
    scaled = dem * z_factor
    best_drop = np.zeros((rows, cols), dtype="float32")
    direction = np.zeros((rows, cols), dtype="uint8")
    receiver = np.full((rows, cols), -1, dtype=np.int64)
    linear = np.arange(rows * cols, dtype=np.int64).reshape(rows, cols)

    for dr, dc, code, _ in _D8_OFFSETS:
        src_slice, dst_slice = _neighbor_slices(dr, dc, rows, cols)
        distance = _neighbor_distance(dr, dc, x_size, y_size)
        src_values = scaled[src_slice]
        dst_values = scaled[dst_slice]
        drop = (src_values - dst_values) / distance
        update = (
            valid_mask[src_slice]
            & valid_mask[dst_slice]
            & np.isfinite(drop)
            & (drop > 0)
            & (drop > best_drop[src_slice])
        )
        if not np.any(update):
            continue

        best_view = best_drop[src_slice]
        direction_view = direction[src_slice]
        receiver_view = receiver[src_slice]
        best_view[update] = drop[update]
        direction_view[update] = code
        receiver_view[update] = linear[dst_slice][update]

    direction[~valid_mask] = 0
    receiver[~valid_mask] = -1
    return direction, receiver


def _neighbor_slices(
    dr: int,
    dc: int,
    rows: int,
    cols: int,
) -> tuple[tuple[slice, slice], tuple[slice, slice]]:
    src_row_start = max(0, -dr)
    src_row_stop = rows - max(0, dr)
    src_col_start = max(0, -dc)
    src_col_stop = cols - max(0, dc)
    dst_row_start = src_row_start + dr
    dst_row_stop = src_row_stop + dr
    dst_col_start = src_col_start + dc
    dst_col_stop = src_col_stop + dc
    return (
        (slice(src_row_start, src_row_stop), slice(src_col_start, src_col_stop)),
        (slice(dst_row_start, dst_row_stop), slice(dst_col_start, dst_col_stop)),
    )


def _neighbor_distance(dr: int, dc: int, x_size: float, y_size: float) -> float:
    if dr != 0 and dc != 0:
        return math.hypot(x_size, y_size)
    if dc != 0:
        return x_size
    return y_size


def _flow_accumulation(receiver: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    flat_receiver = receiver.ravel()
    valid_flat = valid_mask.ravel()
    cell_count = flat_receiver.size
    indegree = np.zeros(cell_count, dtype=np.int32)
    receiver_mask = valid_flat & (flat_receiver >= 0)
    np.add.at(indegree, flat_receiver[receiver_mask], 1)

    accumulation = np.zeros(cell_count, dtype="float64")
    accumulation[valid_flat] = 1.0
    queue = deque(np.flatnonzero(valid_flat & (indegree == 0)).tolist())

    while queue:
        cell = queue.popleft()
        target = flat_receiver[cell]
        if target < 0:
            continue
        accumulation[target] += accumulation[cell]
        indegree[target] -= 1
        if indegree[target] == 0:
            queue.append(int(target))

    return accumulation.reshape(receiver.shape).astype("float32")


def _watershed_labels(receiver: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    flat_receiver = receiver.ravel()
    valid_flat = valid_mask.ravel()
    labels = np.zeros(flat_receiver.size, dtype=np.int32)
    next_label = 1

    for start in np.flatnonzero(valid_flat):
        if labels[start] > 0:
            continue

        path: list[int] = []
        current = int(start)
        while True:
            if labels[current] > 0:
                label = int(labels[current])
                break

            path.append(current)
            target = int(flat_receiver[current])
            if target < 0 or not valid_flat[target]:
                label = next_label
                next_label += 1
                break
            current = target

        for cell in path:
            labels[cell] = label

    return labels.reshape(receiver.shape)


def _prepare_output(
    result: np.ndarray,
    valid_mask: np.ndarray,
    dtype: str,
    nodata: int | float,
) -> np.ndarray:
    if dtype == "uint8":
        output = np.asarray(result, dtype=np.uint8)
        output[~valid_mask] = int(nodata)
        return output
    if dtype == "int32":
        output = np.asarray(result, dtype=np.int32)
        output[~valid_mask] = int(nodata)
        return output

    output = np.asarray(result, dtype="float32")
    output[~valid_mask | ~np.isfinite(output)] = float(nodata)
    return output


def _write_single_band(
    output_path: str,
    profile: dict[str, Any],
    data: np.ndarray,
    dtype: str,
    nodata: int | float,
    description: str,
    operation: str,
) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    profile.update(
        driver="GTiff",
        count=1,
        dtype=dtype,
        nodata=nodata,
        compress="lzw",
    )
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data.astype(dtype), 1)
        dst.set_band_description(1, description)
        dst.update_tags(DEM_ANALYSIS="true", DEM_OPERATION=operation)


def _flow_direction_encoding() -> dict[str, int]:
    return {name: code for _, _, code, name in _D8_OFFSETS}
