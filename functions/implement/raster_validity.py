"""Shared raster-validity and pixel-footprint helpers.

Raster bounds describe the rectangular storage grid. They do not describe
which pixels in that grid contain renderable data. This module keeps those
concepts separate for rendering, point queries, and footprint clipping.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import math
import os
from typing import Iterable

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


def _is_nan(value) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def band_nodata_values(dataset, band_indexes: Iterable[int]) -> list:
    """Return nodata values in the same order as ``band_indexes``."""
    indexes = list(band_indexes)
    nodatavals = getattr(dataset, "nodatavals", None)
    if nodatavals:
        return [
            nodatavals[index - 1]
            if 0 <= index - 1 < len(nodatavals)
            else None
            for index in indexes
        ]
    return [getattr(dataset, "nodata", None)] * len(indexes)


def dataset_has_explicit_mask(dataset, band_indexes: Iterable[int] | None = None) -> bool:
    """Whether validity is explicitly encoded as nodata, alpha, or a GDAL mask."""
    indexes = list(band_indexes or range(1, int(dataset.count) + 1))
    if any(value is not None for value in band_nodata_values(dataset, indexes)):
        return True

    mask_flags = getattr(dataset, "mask_flag_enums", None)
    if not mask_flags:
        return False

    for index in indexes:
        flag_index = index - 1
        if not 0 <= flag_index < len(mask_flags):
            continue
        for flag in mask_flags[flag_index]:
            name = getattr(flag, "name", str(flag)).lower()
            if name in {"alpha", "nodata", "per_dataset"}:
                return True
    return False


def band_validity_mask(
    data: np.ndarray,
    dataset,
    band_indexes: Iterable[int],
    *,
    read_valid_mask: np.ndarray | None = None,
    zero_is_invalid: bool | None = None,
) -> np.ndarray:
    """Return a per-band Boolean mask for renderable numeric samples.

    Explicit GDAL validity metadata always wins. When a raster has no mask,
    alpha, or nodata declaration, zero is treated as implicit background by
    default. ``zero_is_invalid=True`` forces that behavior for explicitly
    masked rasters as well; ``False`` disables the inference.
    """
    indexes = list(band_indexes)
    values = np.asarray(data)
    if values.ndim == 2:
        values = values[np.newaxis, ...]
    if values.ndim != 3 or values.shape[0] != len(indexes):
        raise ValueError("Raster data shape must match the requested band indexes.")

    if read_valid_mask is None:
        valid = np.ones(values.shape, dtype=bool)
    else:
        valid = np.asarray(read_valid_mask, dtype=bool)
        if valid.shape != values.shape:
            valid = np.broadcast_to(valid, values.shape).copy()
        else:
            valid = valid.copy()

    valid &= np.isfinite(values)
    for band_position, nodata in enumerate(band_nodata_values(dataset, indexes)):
        if nodata is None:
            continue
        if _is_nan(nodata):
            valid[band_position] &= ~np.isnan(values[band_position])
        else:
            valid[band_position] &= values[band_position] != float(nodata)

    if zero_is_invalid is None:
        zero_is_invalid = not dataset_has_explicit_mask(dataset, indexes)
    if zero_is_invalid:
        valid &= values != 0
    return valid


def _dataset_windows(dataset):
    try:
        yield from (window for _, window in dataset.block_windows(1))
    except (AttributeError, TypeError, ValueError):
        yield rasterio.windows.Window(0, 0, dataset.width, dataset.height)


def _merge_geometry_parts(parts: list, partial_unions: list) -> None:
    if not parts:
        return
    partial_unions.append(unary_union(parts))
    parts.clear()
    if len(partial_unions) >= 32:
        merged = unary_union(partial_unions)
        partial_unions.clear()
        partial_unions.append(merged)


def compute_valid_pixel_footprint(
    dataset,
    *,
    dst_crs: str | None = "EPSG:4326",
    band_indexes: Iterable[int] | None = None,
) -> dict:
    """Polygonize the exact union of valid source pixels.

    Processing is block-based so memory use is bounded by the raster's block
    size rather than its full dimensions. The resulting Polygon or
    MultiPolygon follows pixel edges; it is not an outer bounding rectangle.
    """
    indexes = list(band_indexes or range(1, int(dataset.count) + 1))
    if not indexes:
        raise ValueError("Raster has no bands.")
    if any(index < 1 or index > dataset.count for index in indexes):
        raise ValueError("A requested raster band index is out of range.")

    geometry_parts: list = []
    partial_unions: list = []
    valid_pixel_count = 0

    for window in _dataset_windows(dataset):
        raw = dataset.read(indexes, window=window, masked=True)
        if np.ma.isMaskedArray(raw):
            read_valid = ~np.ma.getmaskarray(raw)
            data = raw.filled(0)
        else:
            read_valid = None
            data = raw

        per_band_valid = band_validity_mask(
            data,
            dataset,
            indexes,
            read_valid_mask=read_valid,
        )
        pixel_valid = np.any(per_band_valid, axis=0)
        pixel_count = int(np.count_nonzero(pixel_valid))
        if pixel_count == 0:
            continue

        valid_pixel_count += pixel_count
        mask_values = pixel_valid.astype(np.uint8)
        window_transform = dataset.window_transform(window)
        for geojson_geometry, value in shapes(
            mask_values,
            mask=pixel_valid,
            connectivity=4,
            transform=window_transform,
        ):
            if int(value) == 1:
                geometry_parts.append(shape(geojson_geometry))
                if len(geometry_parts) >= 512:
                    _merge_geometry_parts(geometry_parts, partial_unions)

    _merge_geometry_parts(geometry_parts, partial_unions)
    if not partial_unions:
        return {
            "geometry": None,
            "bounds": None,
            "valid_pixel_count": 0,
            "total_pixel_count": int(dataset.width) * int(dataset.height),
        }

    footprint = unary_union(partial_unions)
    source_crs = dataset.crs or "EPSG:4326"
    if (
        dst_crs
        and rasterio.crs.CRS.from_user_input(source_crs)
        != rasterio.crs.CRS.from_user_input(dst_crs)
    ):
        footprint_mapping = transform_geom(
            source_crs,
            dst_crs,
            mapping(footprint),
            antimeridian_cutting=True,
            precision=12,
        )
        footprint = shape(footprint_mapping)

    return {
        "geometry": mapping(footprint),
        "bounds": list(footprint.bounds),
        "valid_pixel_count": valid_pixel_count,
        "total_pixel_count": int(dataset.width) * int(dataset.height),
    }


@lru_cache(maxsize=64)
def _cached_valid_pixel_footprint(
    absolute_path: str,
    modified_time_ns: int,
    dst_crs: str | None,
    band_indexes: tuple[int, ...] | None,
) -> dict:
    del modified_time_ns  # Included in the key to invalidate changed rasters.
    with rasterio.open(absolute_path) as dataset:
        return compute_valid_pixel_footprint(
            dataset,
            dst_crs=dst_crs,
            band_indexes=band_indexes,
        )


def valid_pixel_footprint(
    file_path: str,
    *,
    dst_crs: str | None = "EPSG:4326",
    band_indexes: Iterable[int] | None = None,
) -> dict:
    """Return a cached, mutation-safe valid-pixel footprint for a raster file."""
    absolute_path = os.path.abspath(file_path)
    modified_time_ns = os.stat(absolute_path).st_mtime_ns
    indexes = tuple(band_indexes) if band_indexes is not None else None
    return deepcopy(
        _cached_valid_pixel_footprint(
            absolute_path,
            modified_time_ns,
            dst_crs,
            indexes,
        )
    )
