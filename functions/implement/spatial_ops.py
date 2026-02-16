from rasterio.warp import transform_bounds
import logging

logger = logging.getLogger("functions.spatial_ops")


def get_wgs84_bounds(src_crs, src_bounds):
    if not src_crs:
        return src_bounds

    try:
        bounds_wgs84 = transform_bounds(src_crs, "EPSG:4326", *src_bounds)
        return bounds_wgs84
    except Exception as e:
        logger.warning(f"Spatial transformation failed, falling back to original: {e}")
        return src_bounds


def compute_center_from_bounds(bounds):
    center = [
        (bounds[1] + bounds[3]) / 2,  # Latitude
        (bounds[0] + bounds[2]) / 2  # Longitude
    ]
    return center
