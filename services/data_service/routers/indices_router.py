import logging

from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
import services.data_service.db_ops as db_ops
from services.data_service.processor import RasterProcessor

logger = logging.getLogger("data_service.index")
router = APIRouter()


async def calculate_index_task(
        index_name: str,
        band_ids: list[int],
        new_name: str,
        db: AsyncSession,
        processor_func
) -> dict:
    """通用指数计算入口，委托给 db_ops.process_index_task"""
    return await db_ops.process_index_task(
        db, band_ids, new_name, index_name, processor_func
    )


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/calculate-ndvi")
async def calculate_ndvi_api(
        red_id: int = Form(...),
        nir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await calculate_index_task(
        "ndvi", [red_id, nir_id], new_name, db, RasterProcessor.calculate_ndvi
    )


@router.post("/calculate-ndwi")
async def calculate_ndwi_api(
        green_id: int = Form(...),
        nir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await calculate_index_task(
        "ndwi", [green_id, nir_id], new_name, db, RasterProcessor.calculate_ndwi
    )


@router.post("/calculate-ndbi")
async def calculate_ndbi_api(
        swir_id: int = Form(...),
        nir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await calculate_index_task(
        "ndbi", [swir_id, nir_id], new_name, db, RasterProcessor.calculate_ndbi
    )


@router.post("/calculate-mndwi")
async def calculate_mndwi_api(
        green_id: int = Form(...),
        swir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await calculate_index_task(
        "mndwi", [green_id, swir_id], new_name, db, RasterProcessor.calculate_mndwi
    )
