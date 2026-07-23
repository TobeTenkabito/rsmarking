import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from functions.implement.clip_ops import clip_vector_by_raster

logger = logging.getLogger("annotation_service.spatial")

router = APIRouter(prefix="/spatial", tags=["Spatial"])


class ClipVectorByRasterRequest(BaseModel):
    clip_geometry: dict = Field(
        ...,
        description="GeoJSON valid-pixel raster footprint in EPSG:4326."
    )
    features: list[dict] = Field(
        ...,
        description="GeoJSON Feature object list"
    )
    src_vector_crs: str = Field(
        default="EPSG:4326",
        description="Vector feature coordinate reference system"
    )
    mode: str = Field(
        default="intersects",
        description="Spatial relation mode: intersects | within | clip"
    )


@router.post("/clip-vector-by-raster")
async def clip_vector_by_raster_endpoint(
    body: ClipVectorByRasterRequest,
):
    """
    Clip vector features with the raster valid-pixel footprint.
    In-memory operation that returns a GeoJSON FeatureCollection without writing to the database.
    """
    try:
        return clip_vector_by_raster(
            clip_geometry=body.clip_geometry,
            geojson_features=body.features,
            src_vector_crs=body.src_vector_crs,
            mode=body.mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Raster-to-vector clipping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
