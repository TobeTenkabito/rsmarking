import rasterio
from rasterio.warp import transform_bounds
import numpy as np
import os
import logging


logger = logging.getLogger("data_service.processor")


class RasterProcessor:
    @staticmethod
    def extract_metadata(file_path: str):
        with rasterio.open(file_path) as src:
            crs = src.crs.to_string() if src.crs else "EPSG:4326"
            try:
                bounds_wgs84 = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
            except Exception as e:
                logger.warning(f"坐标转换失败，使用原始边界: {e}")
                bounds_wgs84 = src.bounds

            center = [
                (bounds_wgs84[1] + bounds_wgs84[3]) / 2,
                (bounds_wgs84[0] + bounds_wgs84[2]) / 2
            ]

            return {
                "file_name": os.path.basename(file_path),
                "crs": crs,
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
    def extract_bands(input_path: str, output_path: str, band_indices: list[int]):
        with rasterio.open(input_path) as src:
            out_meta = src.meta.copy()
            out_meta.update({
                "count": len(band_indices),
                "driver": "GTiff"
            })

            with rasterio.open(output_path, "w", **out_meta) as dest:
                for i, band_idx in enumerate(band_indices, start=1):
                    dest.write(src.read(band_idx), i)
        RasterProcessor._build_overviews(output_path)

    @staticmethod
    def merge_bands(input_paths: list[str], output_path: str):
        if not input_paths:
            raise ValueError("输入路径列表不能为空")

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

        RasterProcessor._build_overviews(output_path)


    @staticmethod
    def calculate_ndvi(red_path: str, nir_path: str, output_path: str):
        with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
            meta = red_src.meta.copy()
            meta.update({
                "dtype": "float32",
                "count": 1,
                "driver": "GTiff"
            })

            red = red_src.read(1).astype('float32')
            nir = nir_src.read(1, out_shape=(red_src.height, red_src.width)).astype('float32')
            with np.errstate(divide='ignore', invalid='ignore'):
                ndvi = (nir - red) / (nir + red)
                ndvi = np.nan_to_num(ndvi)

            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(ndvi, 1)
        RasterProcessor._build_overviews(output_path)


    @staticmethod
    def _build_overviews(file_path: str):
        try:
            from osgeo import gdal
            ds = gdal.Open(file_path, gdal.GA_Update)
            if ds:
                ds.BuildOverviews("NEAREST", [2, 4, 8, 16])
                ds = None
                logger.info(f"金字塔构建成功: {file_path}")
        except Exception as e:
            logger.warning(f"GDAL 金字塔构建失败 (不影响基本功能): {e}")

    @staticmethod
    def convert_to_cog(input_path: str, output_path: str):
        from osgeo import gdal

        ds = gdal.Open(input_path)
        if not ds:
            raise Exception(f"无法打开输入文件: {input_path}")
        options = [
            "COMPRESS=LZW",
            "TILED=YES",
            "COPY_SRC_OVERVIEWS=YES",
            "BLOCKSIZE=512"
        ]

        try:
            driver = gdal.GetDriverByName("COG")
            driver.CreateCopy(output_path, ds, options=options)
            logger.info(f"COG 转换完成: {output_path}")
        finally:
            ds = None