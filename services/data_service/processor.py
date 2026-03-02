import os
import logging
from typing import TypedDict, TypeAlias, TypeVar, ParamSpec
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
    def _run_extraction_task(
        paths: list[str],
        output_path: str,
        extraction_func: Callable[[BandList, *P.args], MaskArray],
        min_bands: int,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:

        if len(paths) < min_bands:
            raise ValueError(f"该提取任务至少需要 {min_bands} 个波段路径")

        bands: BandList = []

        with rasterio.open(paths[0]) as first_src:
            meta = first_src.meta.copy()
            meta.update(
                {
                    "dtype": "uint8",
                    "count": 1,
                    "driver": "GTiff",
                }
            )

            height: int = first_src.height
            width: int = first_src.width

            for path in paths:
                with rasterio.open(path) as src:
                    if src.height != height or src.width != width:
                        raise ValueError("波段尺寸不一致，必须预处理对齐")

                    band: BandArray = src.read(1)
                    bands.append(band)

        mask: MaskArray = extraction_func(bands, *args, **kwargs)

        with rasterio.open(output_path, "w", **meta) as dest:
            dest.write(mask.astype("uint8"), 1)

        build_raster_overviews(output_path)

    @staticmethod
    def extract_bands(
        input_path: str,
        output_path: str,
        band_indices: list[int],
    ) -> None:
        extract_raster_bands(input_path, output_path, band_indices)
        build_raster_overviews(output_path)

    @staticmethod
    def merge_bands(
        input_paths: list[str],
        output_path: str,
    ) -> None:
        merge_raster_bands(input_paths, output_path)
        build_raster_overviews(output_path)

    @staticmethod
    def calculate_ndvi(
        red_path: str,
        nir_path: str,
        output_path: str,
    ) -> None:
        with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
            meta = red_src.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})

            red: BandArray = red_src.read(1)
            nir: BandArray = nir_src.read(
                1, out_shape=(red_src.height, red_src.width)
            )

            result: BandArray = calculate_ndvi_array(red, nir)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)

        build_raster_overviews(output_path)

    @staticmethod
    def calculate_ndwi(
        green_path: str,
        nir_path: str,
        output_path: str,
    ) -> None:
        with rasterio.open(green_path) as green_src, rasterio.open(nir_path) as nir_src:
            meta = green_src.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})

            green: BandArray = green_src.read(1)
            nir: BandArray = nir_src.read(
                1, out_shape=(green_src.height, green_src.width)
            )

            result: BandArray = calculate_ndwi_array(green, nir)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)

        build_raster_overviews(output_path)

    @staticmethod
    def calculate_ndbi(
        swir_path: str,
        nir_path: str,
        output_path: str,
    ) -> None:
        with rasterio.open(swir_path) as swir_src, rasterio.open(nir_path) as nir_src:
            meta = swir_src.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})

            swir: BandArray = swir_src.read(1)
            nir: BandArray = nir_src.read(
                1, out_shape=(swir_src.height, swir_src.width)
            )

            result: BandArray = calculate_ndbi_array(swir, nir)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)

        build_raster_overviews(output_path)

    @staticmethod
    def calculate_mndwi(
        green_path: str,
        swir_path: str,
        output_path: str,
    ) -> None:
        with rasterio.open(green_path) as green_src, rasterio.open(swir_path) as swir_src:
            meta = green_src.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})

            green: BandArray = green_src.read(1)
            swir: BandArray = swir_src.read(
                1, out_shape=(green_src.height, green_src.width)
            )

            result: BandArray = calculate_mndwi_array(green, swir)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)

        build_raster_overviews(output_path)

    @staticmethod
    def run_vegetation_extraction(
        paths: list[str],
        output_path: str,
        **kwargs,
    ) -> None:
        RasterProcessor._run_extraction_task(
            paths,
            output_path,
            extract_vegetation,
            min_bands=2,
            **kwargs,
        )

    @staticmethod
    def run_water_extraction(
        paths: list[str],
        output_path: str,
        **kwargs,
    ) -> None:
        RasterProcessor._run_extraction_task(
            paths,
            output_path,
            extract_water,
            min_bands=2,
            **kwargs,
        )

    @staticmethod
    def run_building_extraction(
        paths: list[str],
        output_path: str,
        **kwargs,
    ) -> None:
        RasterProcessor._run_extraction_task(
            paths,
            output_path,
            extract_building,
            min_bands=2,
            **kwargs,
        )

    @staticmethod
    def run_cloud_extraction(
        paths: list[str],
        output_path: str,
        **kwargs,
    ) -> None:
        RasterProcessor._run_extraction_task(
            paths,
            output_path,
            extract_cloud,
            min_bands=1,
            **kwargs,
        )

    @staticmethod
    def convert_to_cog(
        input_path: str,
        output_path: str,
    ) -> None:
        convert_raster_to_cog(input_path, output_path)
