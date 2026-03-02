import os
import logging
from typing import TypedDict, TypeAlias, ParamSpec
from collections.abc import Callable
import numpy as np
import rasterio

from functions.implement.spatial_ops import (
    get_wgs84_bounds,
    compute_center_from_bounds,
)
from functions.implement.spectral_indices import (
    calculate_ndvi_array,
    calculate_ndwi_array,
    calculate_ndbi_array,
    calculate_mndwi_array,
)
from functions.implement.io_ops import (
    build_raster_overviews,
    convert_raster_to_cog,
)
from functions.implement.manipulation import (
    extract_raster_bands,
    merge_raster_bands,
)
from functions.implement.extraction import (
    extract_vegetation,
    extract_water,
    extract_building,
    extract_cloud,
)

logger = logging.getLogger("data_service.processor")

BandArray: TypeAlias = np.ndarray
BandList: TypeAlias = list[BandArray]
MaskArray: TypeAlias = np.ndarray

P = ParamSpec("P")


class MetadataDict(TypedDict):
    file_name: str
    crs: str
    bounds: list[float]
    bounds_wgs84: list[float]
    center: tuple[float, float]
    width: int
    height: int
    bands: int
    data_type: str
    resolution: tuple[float, float]


class RasterProcessor:
    @staticmethod
    def extract_metadata(file_path: str) -> MetadataDict:
        with rasterio.open(file_path) as src:
            crs_str: str = src.crs.to_string() if src.crs else "EPSG:4326"

            bounds_wgs84 = get_wgs84_bounds(src.crs, src.bounds)
            center = compute_center_from_bounds(bounds_wgs84)

            return {
                "file_name": os.path.basename(file_path),
                "crs": crs_str,
                "bounds": list(src.bounds),
                "bounds_wgs84": list(bounds_wgs84),
                "center": center,
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "data_type": src.dtypes[0],
                "resolution": src.res,
            }

    @staticmethod
    def extract_bands(input_path: str, output_path: str, band_indices: list[int],) -> None:
        extract_raster_bands(input_path, output_path, band_indices)
        build_raster_overviews(output_path)

    @staticmethod
    def merge_bands(input_paths: list[str], output_path: str,) -> None:
        merge_raster_bands(input_paths, output_path)
        build_raster_overviews(output_path)

    @staticmethod
    def convert_to_cog(input_path: str, output_path: str,) -> None:
        convert_raster_to_cog(input_path, output_path)

    @staticmethod
    def _run_two_band_index(
        band1_path: str,
        band2_path: str,
        output_path: str,
        index_func: Callable[[BandArray, BandArray], BandArray],
    ) -> None:

        with rasterio.open(band1_path) as src1, rasterio.open(band2_path) as src2:
            meta = src1.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})
            band1: BandArray = src1.read(1)
            band2: BandArray = src2.read(
                1, out_shape=(src1.height, src1.width)
            )
            result: BandArray = index_func(band1, band2)
            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)
        build_raster_overviews(output_path)

    @staticmethod
    def calculate_ndvi(red_path: str, nir_path: str, output_path: str,) -> None:
        RasterProcessor._run_two_band_index(
            red_path, nir_path, output_path, calculate_ndvi_array,)

    @staticmethod
    def calculate_ndwi(green_path: str, nir_path: str, output_path: str,) -> None:
        RasterProcessor._run_two_band_index(
            green_path, nir_path, output_path, calculate_ndwi_array,)

    @staticmethod
    def calculate_ndbi(swir_path: str, nir_path: str, output_path: str,) -> None:
        RasterProcessor._run_two_band_index(
            swir_path, nir_path, output_path, calculate_ndbi_array,)

    @staticmethod
    def calculate_mndwi(green_path: str, swir_path: str, output_path: str,) -> None:
        RasterProcessor._run_two_band_index(
            green_path, swir_path, output_path, calculate_mndwi_array,)

    class _ExtractionRegistry:
        _registry: dict[str, Callable] = {
            "vegetation": extract_vegetation,
            "water": extract_water,
            "building": extract_building,
            "cloud": extract_cloud,
        }

        @classmethod
        def get(cls, name: str) -> Callable:
            if name not in cls._registry:
                raise ValueError(f"Unknown typing: {name}")
            return cls._registry[name]

    @staticmethod
    def _run_extraction_task(
        paths: list[str],
        output_path: str,
        extraction_func: Callable,
        min_bands: int,
        **kwargs,
    ) -> None:

        if len(paths) < min_bands:
            raise ValueError(f"Task needs  {min_bands} bands at least!")
        bands: BandList = []
        with rasterio.open(paths[0]) as first_src:
            meta = first_src.meta.copy()
            meta.update({"dtype": "uint8", "count": 1, "driver": "GTiff"})
            height: int = first_src.height
            width: int = first_src.width
            for path in paths:
                with rasterio.open(path) as src:
                    if src.height != height or src.width != width:
                        raise ValueError("Bands are not consistency!")
                    bands.append(src.read(1))
        mask: MaskArray = extraction_func(bands, **kwargs)
        with rasterio.open(output_path, "w", **meta) as dest:
            dest.write(mask.astype("uint8"), 1)
        build_raster_overviews(output_path)

    @staticmethod
    def run_vegetation_extraction(paths: list[str], output_path: str, **kwargs,) -> None:
        RasterProcessor._run_extraction_task(
            paths, output_path, RasterProcessor._ExtractionRegistry.get("vegetation"), min_bands=2, **kwargs,)

    @staticmethod
    def run_water_extraction(paths: list[str], output_path: str, **kwargs,) -> None:
        RasterProcessor._run_extraction_task(
            paths, output_path, RasterProcessor._ExtractionRegistry.get("water"), min_bands=2, **kwargs,)

    @staticmethod
    def run_building_extraction(paths: list[str], output_path: str, **kwargs,) -> None:
        RasterProcessor._run_extraction_task(
            paths, output_path, RasterProcessor._ExtractionRegistry.get("building"), min_bands=2, **kwargs,)

    @staticmethod
    def run_cloud_extraction(paths: list[str], output_path: str, **kwargs,) -> None:
        RasterProcessor._run_extraction_task(
            paths, output_path, RasterProcessor._ExtractionRegistry.get("cloud"), min_bands=1, **kwargs,)
