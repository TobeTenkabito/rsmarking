import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
from services.data_service.crud.raster_field_crud import RasterFieldCRUD
from services.data_service.raster_field import (
    RasterFieldCreate,
    RasterFieldUpdate,
    RasterFieldOut,
)

logger = logging.getLogger("data_service.field")
router = APIRouter()


@router.get(
    "/raster/{raster_id}/fields",
    response_model=List[RasterFieldOut],
    tags=["RasterField"],
)
async def list_raster_fields(
        raster_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Get all business fields for a raster"""
    crud = RasterFieldCRUD(db)
    return await crud.get_by_raster(raster_id)


@router.post(
    "/raster/{raster_id}/fields",
    response_model=RasterFieldOut,
    tags=["RasterField"],
)
async def create_raster_field(
        raster_id: int,
        field_in: RasterFieldCreate,
        db: AsyncSession = Depends(get_db)
):
    """Add a business field"""
    crud = RasterFieldCRUD(db)
    try:
        return await crud.create(raster_id, field_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/raster/{raster_id}/fields/{field_id}",
    response_model=RasterFieldOut,
    tags=["RasterField"],
)
async def update_raster_field(
        raster_id: int,
        field_id: int,
        field_in: RasterFieldUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Update field alias, type, order, and related settings"""
    crud = RasterFieldCRUD(db)
    updated = await crud.update(field_id, field_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Field not found")
    return updated


@router.delete(
    "/raster/{raster_id}/fields/{field_id}",
    status_code=204,
    tags=["RasterField"],
)
async def delete_raster_field(
        raster_id: int,
        field_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Delete a non-system field"""
    crud = RasterFieldCRUD(db)
    try:
        if not await crud.delete(field_id):
            raise HTTPException(status_code=404, detail="Field not found")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return None
