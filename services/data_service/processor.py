import rasterio
import os
import logging
from typing import List, Callable


from functions.implement.spatial_ops import get_wgs84_bounds, compute_center_from_bounds
from functions.implement.spectral_indices import (
    calculate_ndvi_array,
    calculate_ndwi_array,
    calculate_ndbi_array,
    calculate_mndwi_array
)
from functions.implement.io_ops import build_raster_overviews, convert_raster_to_cog
from functions.implement.manipulation import extract_raster_bands, merge_raster_bands
from functions.implement.extraction import (
    extract_vegetation,
    extract_water,
    extract_building,
    extract_cloud
)

logger = logging.getLogger("data_service.processor")


class RasterProcessor:
    @staticmethod
    def extract_metadata(file_path: str):
        with rasterio.open(file_path) as src:
            crs_str = src.crs.to_string() if src.crs else "EPSG:4326"

            # 调用迁移后的空间算子
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
                "resolution": src.res
            }

    @staticmethod
    def _run_extraction_task(
            paths: List[str],
            output_path: str,
            extraction_func: Callable,
            min_bands: int,
            **kwargs
    ):
        if len(paths) < min_bands:
            raise ValueError(f"该提取任务至少需要 {min_bands} 个波段路径")
        bands = []
        with rasterio.open(paths[0]) as first_src:
            meta = first_src.meta.copy()
            meta.update({
                "dtype": "uint8",
                "count": 1,
                "driver": "GTiff"
            })
            h, w = first_src.height, first_src.width
            for path in paths:
                with rasterio.open(path) as src:
                    if src.height != h or src.width != w:
                        raise ValueError("波段尺寸不一致，必须预处理对齐")
                    bands.append(src.read(1))
        mask = extraction_func(bands, **kwargs)
        with rasterio.open(output_path, "w", **meta) as dest:
            dest.write(mask.astype("uint8"), 1)
        build_raster_overviews(output_path)

    @staticmethod
    def extract_bands(input_path: str, output_path: str, band_indices: List[int]):
        extract_raster_bands(input_path, output_path, band_indices)
        build_raster_overviews(output_path)

    @staticmethod
    def merge_bands(input_paths: List[str], output_path: str):
        merge_raster_bands(input_paths, output_path)
        build_raster_overviews(output_path)

    @staticmethod
    def calculate_ndvi(red_path: str, nir_path: str, output_path: str):
        """
        计算归一化植被指数 (NDVI)
        """
        with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
            meta = red_src.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})

            red = red_src.read(1)
            nir = nir_src.read(1, out_shape=(red_src.height, red_src.width))

            result = calculate_ndvi_array(red, nir)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)
        build_raster_overviews(output_path)

    @staticmethod
    def calculate_ndwi(green_path: str, nir_path: str, output_path: str):
        """
        计算归一化水体指数 (NDWI)
        """
        with rasterio.open(green_path) as green_src, rasterio.open(nir_path) as nir_src:
            meta = green_src.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})

            green = green_src.read(1)
            nir = nir_src.read(1, out_shape=(green_src.height, green_src.width))

            result = calculate_ndwi_array(green, nir)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)
        build_raster_overviews(output_path)

    @staticmethod
    def calculate_ndbi(swir_path: str, nir_path: str, output_path: str):
        """
        计算归一化建筑指数 (NDBI)
        """
        with rasterio.open(swir_path) as swir_src, rasterio.open(nir_path) as nir_src:
            meta = swir_src.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})

            swir = swir_src.read(1)
            nir = nir_src.read(1, out_shape=(swir_src.height, swir_src.width))

            result = calculate_ndbi_array(swir, nir)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)
        build_raster_overviews(output_path)

    @staticmethod
    def calculate_mndwi(green_path: str, swir_path: str, output_path: str):
        """
        计算改进型归一化水体指数 (MNDWI)
        """
        with rasterio.open(green_path) as green_src, rasterio.open(swir_path) as swir_src:
            meta = green_src.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})

            green = green_src.read(1)
            swir = swir_src.read(1, out_shape=(green_src.height, green_src.width))

            result = calculate_mndwi_array(green, swir)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)
        build_raster_overviews(output_path)

    @staticmethod
    def run_vegetation_extraction(paths: List[str], output_path: str, **kwargs):
        RasterProcessor._run_extraction_task(
            paths, output_path, extract_vegetation, min_bands=2, **kwargs
        )

    @staticmethod
    def run_water_extraction(paths: List[str], output_path: str, **kwargs):
        RasterProcessor._run_extraction_task(
            paths, output_path, extract_water, min_bands=2, **kwargs
        )

    @staticmethod
    def run_building_extraction(paths: List[str], output_path: str, **kwargs):
        RasterProcessor._run_extraction_task(
            paths, output_path, extract_building, min_bands=2, **kwargs
        )

    @staticmethod
    def run_cloud_extraction(paths: List[str], output_path: str, **kwargs):
        RasterProcessor._run_extraction_task(
            paths, output_path, extract_cloud, min_bands=1, **kwargs
        )

    @staticmethod
    def _build_overviews(file_path: str):
        build_raster_overviews(file_path)

    @staticmethod
    def convert_to_cog(input_path: str, output_path: str):
        convert_raster_to_cog(input_path, output_path)
        
