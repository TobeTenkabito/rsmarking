import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from functions.implement.clip_ops import clip_vector_by_raster

logger = logging.getLogger("annotation_service.spatial")

router = APIRouter(prefix="/spatial", tags=["Spatial"])


class ClipVectorByRasterRequest(BaseModel):
    clip_geometry: dict = Field(
        ...,
        description="GeoJSON Geometry 对象，由前端从栅格 bounds_wgs84 构造，坐标系为 EPSG:4326"
    )
    features: list[dict] = Field(
        ...,
        description="GeoJSON Feature 对象列表"
    )
    src_vector_crs: str = Field(
        default="EPSG:4326",
        description="矢量要素的坐标系"
    )
    mode: str = Field(
        default="intersects",
        description="空间关系模式: intersects | within | clip"
    )


@router.post("/clip-vector-by-raster")
async def clip_vector_by_raster_endpoint(
    body: ClipVectorByRasterRequest,
):
    """
    用栅格空间范围裁剪矢量要素。
    纯内存操作，直接返回 GeoJSON FeatureCollection，不写库。
    前端从已有的 bounds_wgs84 构造 clip_geometry 传入，无需查询栅格服务。
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
        logger.error(f"栅格裁剪矢量失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
