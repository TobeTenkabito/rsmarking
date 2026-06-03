from pydantic import BaseModel


class ClipRasterByVectorRequest(BaseModel):
    """clip"""
    raster_id: int                        # clip ID
    new_name: str                         # text
    geometries: list[dict]                # GeoJSON geometry objecttable
    src_vector_crs: str = "EPSG:4326"     # coordinates
    crop: bool = True                     # clip
    nodata: float | None = None           # text
    all_touched: bool = False             # text


class ClipVectorByRasterRequest(BaseModel):
    """clip"""
    raster_id: int                        # text ID
    features: list[dict]                  # GeoJSON Feature objecttable
    src_vector_crs: str = "EPSG:4326"     # coordinates
    mode: str = "intersects"              # intersects / within / clip
