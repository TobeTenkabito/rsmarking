import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.database import get_db


logger = logging.getLogger("data_service.preprocessing")
router = APIRouter()


@router.post("/radiometric-calibration")
async def radiometric_calibration(
    raster_id: int = Form(...),
    new_name: str = Form(...),
    calibration_type: Literal["auto", "radiance", "reflectance", "scale"] = Form("auto"),
    scale_factor: float | None = Form(None),
    offset: float | None = Form(None),
    radiance_mult: float | None = Form(None),
    radiance_add: float | None = Form(None),
    reflectance_mult: float | None = Form(None),
    reflectance_add: float | None = Form(None),
    sun_elevation: float | None = Form(None),
    earth_sun_distance: float = Form(1.0),
    solar_irradiance: float | None = Form(None),
    sun_elevation_correction: bool = Form(True),
    clamp: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_radiometric_calibration_task(
        db=db,
        raster_id=raster_id,
        new_name=new_name,
        calibration_type=calibration_type,
        scale_factor=scale_factor,
        offset=offset,
        radiance_mult=radiance_mult,
        radiance_add=radiance_add,
        reflectance_mult=reflectance_mult,
        reflectance_add=reflectance_add,
        sun_elevation=sun_elevation,
        earth_sun_distance=earth_sun_distance,
        solar_irradiance=solar_irradiance,
        sun_elevation_correction=sun_elevation_correction,
        clamp=clamp,
    )


@router.post("/geometric-correction")
async def geometric_correction(
    raster_id: int = Form(...),
    new_name: str = Form(...),
    dst_crs: str | None = Form(None),
    resampling_method: str = Form("bilinear"),
    target_resolution_x: float | None = Form(None),
    target_resolution_y: float | None = Form(None),
    shift_x: float = Form(0.0),
    shift_y: float = Form(0.0),
    scale_x: float = Form(1.0),
    scale_y: float = Form(1.0),
    rotation_degrees: float = Form(0.0),
    gcps: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_geometric_correction_task(
        db=db,
        raster_id=raster_id,
        new_name=new_name,
        dst_crs=_blank_to_none(dst_crs),
        resampling_method=resampling_method,
        target_resolution_x=target_resolution_x,
        target_resolution_y=target_resolution_y,
        shift_x=shift_x,
        shift_y=shift_y,
        scale_x=scale_x,
        scale_y=scale_y,
        rotation_degrees=rotation_degrees,
        gcps=_parse_gcps(gcps),
    )


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_gcps(value: str | None) -> list[dict[str, float]] | None:
    if not value or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"gcps must be valid JSON: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise HTTPException(status_code=400, detail="gcps must be a JSON array of objects")
    return [_coerce_gcp(item) for item in parsed]


def _coerce_gcp(item: dict[str, Any]) -> dict[str, float]:
    try:
        return {
            "row": float(item["row"]),
            "col": float(item["col"]),
            "x": float(item["x"]),
            "y": float(item["y"]),
        }
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="Each GCP must include row, col, x, and y") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="GCP row, col, x, and y must be numeric") from exc
