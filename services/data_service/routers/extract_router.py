import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
import services.data_service.db_ops as db_ops
from services.data_service.processor import RasterProcessor

logger = logging.getLogger("data_service.extract")
router = APIRouter()


@router.post("/extract-vegetation")
async def extract_vegetation_api(
        request: Request,
        new_name: str = Form(...),
        threshold: float = Form(None),
        mode: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    band_ids = await db_ops.get_dynamic_band_ids(request)
    if not band_ids:
        raise HTTPException(status_code=400, detail="No band IDs provided.")
    return await db_ops.process_extraction_task(
        db, band_ids, new_name, "veg",
        RasterProcessor.run_vegetation_extraction,
        threshold=threshold,
        mode=mode
    )


@router.post("/extract-water")
async def extract_water_api(
        request: Request,
        new_name: str = Form(...),
        threshold: float = Form(None),
        mode: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    band_ids = await db_ops.get_dynamic_band_ids(request)
    if not band_ids:
        raise HTTPException(status_code=400, detail="No band IDs provided.")
    return await db_ops.process_extraction_task(
        db, band_ids, new_name, "water",
        RasterProcessor.run_water_extraction,
        threshold=threshold,
        mode=mode
    )


@router.post("/extract-buildings")
async def extract_buildings_api(
        request: Request,
        new_name: str = Form(...),
        threshold: float = Form(None),
        mode: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    band_ids = await db_ops.get_dynamic_band_ids(request)
    if not band_ids:
        raise HTTPException(status_code=400, detail="No band IDs provided.")
    return await db_ops.process_extraction_task(
        db, band_ids, new_name, "building",
        RasterProcessor.run_building_extraction,
        threshold=threshold,
        mode=mode
    )


@router.post("/extract-clouds")
async def extract_clouds_api(
        request: Request,
        new_name: str = Form(...),
        threshold: float = Form(None),
        mode: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    band_ids = await db_ops.get_dynamic_band_ids(request)
    if not band_ids:
        raise HTTPException(status_code=400, detail="No band IDs provided.")
    return await db_ops.process_extraction_task(
        db, band_ids, new_name, "cloud",
        RasterProcessor.run_cloud_extraction,
        threshold=threshold,
        mode=mode
    )
