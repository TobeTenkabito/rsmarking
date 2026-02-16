import rasterio
import logging
from typing import List

logger = logging.getLogger("functions.manipulation")


def extract_raster_bands(input_path: str, output_path: str, band_indices: List[int]):
    with rasterio.open(input_path) as src:
        out_meta = src.meta.copy()
        out_meta.update({
            "count": len(band_indices),
            "driver": "GTiff"
        })

        with rasterio.open(output_path, "w", **out_meta) as dest:
            for i, band_idx in enumerate(band_indices, start=1):
                dest.write(src.read(band_idx), i)
    return True


def merge_raster_bands(input_paths: List[str], output_path: str):
    if not input_paths:
        raise ValueError("Input paths list cannot be empty")

    with rasterio.open(input_paths[0]) as first:
        meta = first.meta.copy()
        meta.update({
            "count": len(input_paths),
            "driver": "GTiff"
        })
        with rasterio.open(output_path, "w", **meta) as dest:
            for i, path in enumerate(input_paths, start=1):
                with rasterio.open(path) as src:
                    dest.write(
                        src.read(1, out_shape=(first.height, first.width)),
                        i
                    )
    return True
