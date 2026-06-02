import logging
from typing import Literal

from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.database import get_db


logger = logging.getLogger("data_service.atmospheric")
router = APIRouter()


@router.post("/atmospheric-correction")
async def atmospheric_correction(
    raster_id: int = Form(...),
    method: Literal[
        "auto",
        "surface_reflectance",
        "metadata_scale",
        "dos1",
        "quac",
        "lasrc",
        "ledaps",
        "sen2cor",
        "modis_sr",
        "flaash",
        "sixs",
    ] = Form("auto"),
    sensor: Literal["auto", "landsat", "sentinel2", "modis", "gaofen", "generic"] = Form("auto"),
    new_name: str = Form(...),
    scale_factor: float | None = Form(None),
    offset: float | None = Form(None),
    dark_percentile: float = Form(1.0),
    bright_percentile: float = Form(99.0),
    clamp: bool = Form(True),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_atmospheric_correction_task(
        db=db,
        raster_id=raster_id,
        method=method,
        sensor=sensor,
        new_name=new_name,
        scale_factor=scale_factor,
        offset=offset,
        dark_percentile=dark_percentile,
        bright_percentile=bright_percentile,
        clamp=clamp,
    )
