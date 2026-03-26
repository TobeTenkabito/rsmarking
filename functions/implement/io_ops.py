import logging
import os
from osgeo import gdal


gdal.UseExceptions()
logger = logging.getLogger("functions.io_ops")


def build_raster_overviews(file_path: str, levels: list = [2, 4, 8, 16], resampling: str = "NEAREST"):
    # 开启所有 CPU 核心进行概览图计算
    gdal.SetConfigOption("GDAL_NUM_THREADS", "ALL_CPUS")
    gdal.SetConfigOption("COMPRESS_OVERVIEW", "LZW")

    try:
        ds = gdal.Open(file_path, gdal.GA_Update)
        ds.BuildOverviews(resampling, levels)
        ds = None
        logger.info(f"Overviews built successfully for: {file_path}")
        return True
    except Exception as e:
        logger.warning(f"GDAL overview build failed: {e}")
        return False
    finally:
        # 清理环境变量，避免污染同一进程内的其他 GDAL 任务
        gdal.SetConfigOption("GDAL_NUM_THREADS", None)
        gdal.SetConfigOption("COMPRESS_OVERVIEW", None)


def convert_raster_to_cog(input_path: str, output_path: str, block_size: int = 512):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    ds = None
    try:
        ds = gdal.Open(input_path, gdal.GA_ReadOnly)
        if ds is None:
            raise Exception(f"Could not open input file: {input_path}")
        if ds.GetRasterBand(1).GetOverviewCount() == 0:
            logger.info("Source has no overviews, building before COG conversion...")
            ds.FlushCache()
            ds = None
            build_raster_overviews(input_path)
            ds = gdal.Open(input_path, gdal.GA_ReadOnly)
        cog_options = [
            "COMPRESS=LZW",
            "TILED=YES",
            "COPY_SRC_OVERVIEWS=YES",
            f"BLOCKXSIZE={block_size}",
            f"BLOCKYSIZE={block_size}",
            "NUM_THREADS=ALL_CPUS",
            "BIGTIFF=IF_SAFER",
        ]
        driver = gdal.GetDriverByName("COG")
        use_cog_driver = driver is not None
        if not use_cog_driver:
            logger.warning("COG driver not found, falling back to GTiff")
            driver = gdal.GetDriverByName("GTiff")
            cog_options = [
                "COMPRESS=LZW",
                "TILED=YES",
                f"BLOCKXSIZE={block_size}",
                f"BLOCKYSIZE={block_size}",
                "INTERLEAVE=PIXEL",
                "BIGTIFF=IF_SAFER",
            ]
        result_ds = driver.CreateCopy(output_path, ds, strict=0, options=cog_options)
        if result_ds is None:
            raise Exception(f"CreateCopy returned None, COG conversion failed for: {input_path}")
        result_ds.FlushCache()
        result_ds = None
        logger.info(f"COG conversion completed: {output_path}")
        return True
    except Exception as e:
        logger.error(f"COG conversion failed: {e}")
        raise
    finally:
        if ds is not None:
            ds.FlushCache()
            ds = None
