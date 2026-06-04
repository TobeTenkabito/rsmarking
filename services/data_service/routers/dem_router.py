import logging
from typing import Literal

from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.database import get_db


logger = logging.getLogger("data_service.dem")
router = APIRouter()


DEMOperation = Literal[
    "elevation",
    "slope",
    "aspect",
    "hillshade",
    "curvature",
    "relief",
    "twi",
    "flow_direction",
    "flow_accumulation",
    "watershed",
]


@router.post("/dem-analysis")
async def dem_analysis(
    raster_id: int = Form(...),
    operation: DEMOperation = Form(...),
    new_name: str = Form(...),
    band_index: int = Form(1),
    z_factor: float = Form(1.0),
    slope_unit: str = Form("degrees"),
    hillshade_azimuth: float = Form(315.0),
    hillshade_altitude: float = Form(45.0),
    relief_window_size: int = Form(3),
    min_slope_degrees: float = Form(0.1),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_dem_analysis_task(
        db=db,
        raster_id=raster_id,
        operation=operation,
        new_name=new_name,
        band_index=band_index,
        z_factor=z_factor,
        slope_unit=slope_unit,
        hillshade_azimuth=hillshade_azimuth,
        hillshade_altitude=hillshade_altitude,
        relief_window_size=relief_window_size,
        min_slope_degrees=min_slope_degrees,
    )
