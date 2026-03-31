import os
import uuid
import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from services.data_service.database import get_db
import services.data_service.models as models
import services.data_service.db_ops as db_ops
from services.data_service.processor import RasterProcessor
from services.data_service.schemas import ClipRasterByVectorRequest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")

logger = logging.getLogger("data_service.clip")
router = APIRouter()


@router.post("/clip-raster-by-vector")
async def clip_raster_by_vector(
        body: ClipRasterByVectorRequest,
        db: AsyncSession = Depends(get_db),
):
    """用矢量多边形裁剪栅格，结果注册为新栅格记录走 COG 流程"""
    result = await db.execute(
        select(models.RasterMetadata).where(
            models.RasterMetadata.index_id == body.raster_id
        )
    )
    raster_record = result.scalars().first()
    if not raster_record:
        raise HTTPException(status_code=404, detail="栅格不存在")

    output_id = str(uuid.uuid4())
    output_name = (
        body.new_name if body.new_name.endswith(".tif") else f"{body.new_name}.tif"
    )
    tmp_path = os.path.join(UPLOAD_DIR, f"{output_id}_clip.tif")
    cog_filename = f"{output_id}_{output_name}"
    cog_path = os.path.join(COG_DIR, cog_filename)

    try:
        clip_meta = RasterProcessor.clip_raster_by_vector(
            raster_path=raster_record.file_path,
            output_path=tmp_path,
            geojson_geometries=body.geometries,
            src_vector_crs=body.src_vector_crs,
            crop=body.crop,
            nodata=body.nodata,
            all_touched=body.all_touched,
        )

        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        db_result = await db_ops.save_to_db(
            db, output_id, output_name, tmp_path,
            cog_filename, cog_path, "clip_raster",
            bands_count=clip_meta["bands"],
            metadata_source=tmp_path,
        )

        return {
            "status": "success",
            "id": db_result["id"],
            "clip_meta": clip_meta,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"矢量裁剪栅格失败: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
