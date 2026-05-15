import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
import services.data_service.db_ops as db_ops
from services.data_service.processor import RasterProcessor
from services.data_service.bridges.vector_bridge import internal_fetch_features

logger = logging.getLogger("data_service.rasterize")
router = APIRouter(prefix="/rasterize", tags=["Analysis"])


@router.post("/layer-to-raster")
async def layer_to_raster_api(
    layer_id: UUID = Form(...),
    ref_index_id: int = Form(...),
    new_name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Rasterize the specified vector layer using the reference image's resolution and extent.
    """
    return await db_ops.process_rasterize_task(
        db=db,
        layer_id=layer_id,
        ref_index_id=ref_index_id,
        new_name=new_name,
        prefix="rasterized",
        processor_func=RasterProcessor.run_rasterization,
        fetch_func=internal_fetch_features
    )


@router.post("/raster-to-vector")
async def raster_to_vector_api(
    raster_index_id: int = Form(...),
    project_id: UUID = Form(...),
    new_name: str = Form(...),
    band_index: int = Form(1),
    skip_nodata: bool = Form(True),
    skip_zero: bool = Form(True),
    max_features: int = Form(10000),
    simplify_tolerance: float = Form(0.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Polygonize a raster band and store the generated polygons in a new vector layer.
    """
    return await db_ops.process_raster_to_vector_task(
        db=db,
        raster_index_id=raster_index_id,
        project_id=project_id,
        new_name=new_name,
        band_index=band_index,
        skip_nodata=skip_nodata,
        skip_zero=skip_zero,
        max_features=max_features,
        simplify_tolerance=simplify_tolerance,
    )
