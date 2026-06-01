import logging

from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.database import get_db


logger = logging.getLogger("data_service.resample")
router = APIRouter()


@router.post("/resample-raster")
async def resample_raster(
    raster_id: int = Form(...),
    target_resolution_x: float = Form(...),
    target_resolution_y: float | None = Form(None),
    resolution_unit: str = Form("source"),
    resampling_method: str = Form("bilinear"),
    new_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_resampling_task(
        db=db,
        raster_id=raster_id,
        target_resolution_x=target_resolution_x,
        target_resolution_y=target_resolution_y,
        resolution_unit=resolution_unit,
        resampling_method=resampling_method,
        new_name=new_name,
    )
