import logging
from typing import List

import rasterio

logger = logging.getLogger("functions.manipulation")


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
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(src.read(band_indices))
    return True


def merge_raster_bands(input_paths: List[str], output_path: str) -> bool:
    if not input_paths:
        raise ValueError("Input paths list cannot be empty")

    total_bands = 0
    for p in input_paths:
        with rasterio.open(p) as src:
            total_bands += src.count

    with rasterio.open(input_paths[0]) as first:
        meta = first.meta.copy()
        height = first.height
        width = first.width
        meta.update({
            "count": total_bands,
            "driver": "GTiff",
        })

    with rasterio.open(output_path, "w", **meta) as dest:
        band_idx = 1
        for path in input_paths:
            with rasterio.open(path) as src:
                data = src.read(out_shape=(src.count, height, width))
                indexes = list(range(band_idx, band_idx + src.count))
                dest.write(data, indexes=indexes)
                band_idx += src.count
    return True
