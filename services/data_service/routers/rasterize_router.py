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
    将指定的矢量图层根据参考影像的分辨率和范围进行栅格化
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