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

    try:
        ds = gdal.Open(input_path)
    except Exception as e:
        raise Exception(f"Could not open input file for COG conversion: {input_path}. Error: {e}")

    options = [
        "COMPRESS=LZW",
        "TILED=YES",
        "COPY_SRC_OVERVIEWS=YES",
        f"BLOCKSIZE={block_size}",
        "NUM_THREADS=ALL_CPUS"
    ]

    try:
        driver = gdal.GetDriverByName("COG")
        if not driver:
            logger.warning("COG driver not found, falling back to GTiff with COG-compliant options")
            driver = gdal.GetDriverByName("GTiff")
            options.append("INTERLEAVE=PIXEL")

        driver.CreateCopy(output_path, ds, options=options)
        logger.info(f"COG conversion completed: {output_path}")
        return True
    except Exception as e:
        logger.warning(f"COG conversion failed: {e}")
        return False
    finally:
        ds = None