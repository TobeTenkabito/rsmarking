import logging
from osgeo import gdal

logger = logging.getLogger("functions.io_ops")


def build_raster_overviews(file_path: str, levels: list = [2, 4, 8, 16], resampling: str = "NEAREST"):
    try:
        ds = gdal.Open(file_path, gdal.GA_Update)
        if ds:
            ds.BuildOverviews(resampling, levels)
            ds = None
            logger.info(f"Overviews built successfully for: {file_path}")
            return True
    except Exception as e:
        logger.warning(f"GDAL overview build failed: {e}")
        return False


def convert_raster_to_cog(input_path: str, output_path: str, block_size: int = 512):
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ds = gdal.Open(input_path)
    if not ds:
        raise Exception(f"Could not open input file for COG conversion: {input_path}")

    options = [
        "COMPRESS=LZW",
        "TILED=YES",
        "COPY_SRC_OVERVIEWS=YES",
        "BLOCKSIZE=" + str(block_size)
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
    finally:
        ds = None
