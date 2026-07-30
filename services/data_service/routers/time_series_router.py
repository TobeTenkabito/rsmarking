from datetime import datetime, timezone
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.database import get_db
from services.data_service.temporal_series import build_time_series_candidates


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


class TemporalMetadataUpdate(BaseModel):
    acquired_at: datetime | None = None
    acquired_at_end: datetime | None = None
    platform: str | None = Field(default=None, max_length=100)
    sensor: str | None = Field(default=None, max_length=100)
    product_id: str | None = Field(default=None, max_length=255)
    processing_level: str | None = Field(default=None, max_length=100)
    tile_id: str | None = Field(default=None, max_length=100)

    @field_validator("acquired_at", "acquired_at_end")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_range(self) -> "TemporalMetadataUpdate":
        if (
            self.acquired_at
            and self.acquired_at_end
            and self.acquired_at_end < self.acquired_at
        ):
            raise ValueError("acquired_at_end must not be before acquired_at")
        return self


@router.get("/time-series-candidates")
async def time_series_candidates(db: AsyncSession = Depends(get_db)):
    records = await RasterCRUD.get_all_rasters(db)
    candidates = build_time_series_candidates(records)
    return {
        "candidates": candidates,
        "candidate_count": len(candidates),
    }


@router.patch("/raster/{raster_id}/temporal-metadata")
async def update_temporal_metadata(
    raster_id: int,
    payload: TemporalMetadataUpdate,
    db: AsyncSession = Depends(get_db),
):
    record = await RasterCRUD.get_raster_by_index_id(db, raster_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Raster not found")

    update_data = payload.model_dump(exclude_unset=True)
    next_start = (
        payload.acquired_at
        if "acquired_at" in payload.model_fields_set
        else record.acquired_at
    )
    next_end = (
        payload.acquired_at_end
        if "acquired_at_end" in payload.model_fields_set
        else record.acquired_at_end
    )
    if next_start and next_end and next_end < next_start:
        raise HTTPException(
            status_code=422,
            detail="acquired_at_end must not be before acquired_at",
        )

    if "acquired_at" in payload.model_fields_set:
        if payload.acquired_at is None:
            update_data.update(
                acquired_at_source="unknown",
                acquired_at_confidence=0.0,
            )
        else:
            update_data.update(
                acquired_at_source="user",
                acquired_at_confidence=1.0,
            )
    updated = await RasterCRUD.update_raster(db, raster_id, update_data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Raster not found")
    return updated


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
