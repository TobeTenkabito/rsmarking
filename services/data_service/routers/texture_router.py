import logging
from typing import Literal

from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.database import get_db


logger = logging.getLogger("data_service.texture")
router = APIRouter()


TextureType = Literal["glcm", "local_statistics", "gabor", "lbp"]
GLCMProperty = Literal[
    "contrast",
    "dissimilarity",
    "homogeneity",
    "asm",
    "energy",
    "entropy",
    "correlation",
]
LocalStatistic = Literal["mean", "std", "variance", "range", "entropy"]


@router.post("/texture-feature-analysis")
async def texture_feature_analysis(
    raster_id: int = Form(...),
    texture_type: TextureType = Form(...),
    new_name: str = Form(...),
    band_index: int = Form(1),
    gray_levels: int = Form(32),
    window_size: int = Form(7),
    glcm_distance: int = Form(1),
    glcm_angle: float = Form(0.0),
    glcm_property: GLCMProperty = Form("contrast"),
    local_stat: LocalStatistic = Form("mean"),
    gabor_frequency: float = Form(0.2),
    gabor_theta: float = Form(0.0),
    gabor_sigma: float = Form(2.0),
    lbp_radius: float = Form(1.0),
    lbp_points: int = Form(8),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_texture_feature_task(
        db=db,
        raster_id=raster_id,
        texture_type=texture_type,
        new_name=new_name,
        band_index=band_index,
        gray_levels=gray_levels,
        window_size=window_size,
        glcm_distance=glcm_distance,
        glcm_angle=glcm_angle,
        glcm_property=glcm_property,
        local_stat=local_stat,
        gabor_frequency=gabor_frequency,
        gabor_theta=gabor_theta,
        gabor_sigma=gabor_sigma,
        lbp_radius=lbp_radius,
        lbp_points=lbp_points,
    )
