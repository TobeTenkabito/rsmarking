import logging
import math
from typing import List

import numpy as np
import rasterio
from rasterio.enums import Resampling

from functions.implement.raster_validity import (
    read_masked_data,
    read_masked_on_grid,
    write_dataset_mask,
)

logger = logging.getLogger("functions.manipulation")


def _nodata_values_equal(left, right) -> bool:
    if left is None or right is None:
        return left is right
    try:
        if math.isnan(float(left)) and math.isnan(float(right)):
            return True
    except (TypeError, ValueError):
        pass
    return left == right


def extract_raster_bands(input_path: str, output_path: str, band_indices: List[int]) -> bool:
    with rasterio.open(input_path) as src:
        invalid = [i for i in band_indices if i < 1 or i > src.count]
        if invalid:
            raise ValueError(
                f"Band index out of range: {invalid}; file has {src.count} band(s)"
            )

        out_meta = src.meta.copy()
        out_meta.update({
            "count": len(band_indices),
            "driver": "GTiff",
        })
        selected = read_masked_data(
            src,
            band_indices,
            zero_is_invalid=None,
        )
        fill_value = src.nodata if src.nodata is not None else 0
        valid_pixels = np.any(~np.ma.getmaskarray(selected), axis=0)
        with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(selected.filled(fill_value))
                write_dataset_mask(dest, valid_pixels)
                for output_index, source_index in enumerate(band_indices, start=1):
                    description = src.descriptions[source_index - 1]
                    if description:
                        dest.set_band_description(output_index, description)
    return True


def merge_raster_bands(input_paths: List[str], output_path: str) -> bool:
    if not input_paths:
        raise ValueError("Input paths list cannot be empty")

    total_bands = 0
    source_nodata_values = []
    for p in input_paths:
        with rasterio.open(p) as src:
            total_bands += src.count
            source_nodata_values.append(src.nodata)

    with rasterio.open(input_paths[0]) as first:
        meta = first.meta.copy()
        height = first.height
        width = first.width
        common_nodata = source_nodata_values[0]
        if any(
            not _nodata_values_equal(value, common_nodata)
            for value in source_nodata_values[1:]
        ):
            common_nodata = None
        meta.update({
            "count": total_bands,
            "driver": "GTiff",
        })
        if common_nodata is None:
            meta.pop("nodata", None)
        else:
            meta["nodata"] = common_nodata

        output_valid = np.ones((height, width), dtype=bool)
        fill_value = common_nodata if common_nodata is not None else 0
        with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
            with rasterio.open(output_path, "w", **meta) as dest:
                band_idx = 1
                for path in input_paths:
                    with rasterio.open(path) as src:
                        masked = read_masked_on_grid(
                            src,
                            first,
                            list(range(1, src.count + 1)),
                            resampling=Resampling.nearest,
                            zero_is_invalid=None,
                        )
                        indexes = list(range(band_idx, band_idx + src.count))
                        dest.write(masked.filled(fill_value), indexes=indexes)
                        output_valid &= np.any(
                            ~np.ma.getmaskarray(masked),
                            axis=0,
                        )
                        for offset, description in enumerate(src.descriptions):
                            if description:
                                dest.set_band_description(
                                    band_idx + offset,
                                    description,
                                )
                        band_idx += src.count
                write_dataset_mask(dest, output_valid)
    return True
