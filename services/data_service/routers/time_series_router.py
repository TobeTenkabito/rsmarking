import logging
from typing import Literal

from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.database import get_db


logger = logging.getLogger("data_service.time_series")
router = APIRouter()


TimeSeriesOperation = Literal[
    "monthly_composite",
    "annual_composite",
    "maximum_composite",
    "median_composite",
    "moving_window_smoothing",
    "savitzky_golay",
    "trend",
    "seasonality",
    "phenology",
]


@router.post("/time-series-analysis")
async def time_series_analysis(
    raster_ids: str = Form(...),
    operation: TimeSeriesOperation = Form(...),
    new_name: str = Form(...),
    band_index: int = Form(1),
    dates: str = Form(""),
    moving_window_size: int = Form(3),
    savgol_window_length: int = Form(5),
    savgol_polyorder: int = Form(2),
    phenology_threshold_ratio: float = Form(0.2),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_time_series_task(
        db=db,
        raster_ids=raster_ids,
        operation=operation,
        new_name=new_name,
        band_index=band_index,
        dates=dates,
        moving_window_size=moving_window_size,
        savgol_window_length=savgol_window_length,
        savgol_polyorder=savgol_polyorder,
        phenology_threshold_ratio=phenology_threshold_ratio,
    )
