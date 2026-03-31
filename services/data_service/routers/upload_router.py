import os
import shutil
import uuid
import logging

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from services.data_service.database import get_db
import services.data_service.models as models
import services.data_service.db_ops as db_ops
from services.data_service.processor import RasterProcessor

# Constants
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")

logger = logging.getLogger("data_service.upload")
router = APIRouter()


async def save_and_process_file(
        file: UploadFile,
        db: AsyncSession,
        background_tasks: BackgroundTasks,
        bundle_id: str = None
) -> dict:
    """保存上传文件并提取元数据，后台启动 COG 转换"""
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    raw_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    cog_filename = f"{file_id}.tif"
    cog_path = os.path.join(COG_DIR, cog_filename)

    try:
        with open(raw_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        metadata = RasterProcessor.extract_metadata(raw_path)
        result = await db_ops.save_to_db(
            db, file_id, file.filename, raw_path, cog_filename, cog_path,
            "upload", bundle_id=bundle_id,
            bands_count=metadata.get("bands", 1),
            metadata_source=raw_path
        )

        background_tasks.add_task(db_ops.run_conversion, raw_path, cog_path)
        return {"id": result["id"], "status": "processing", "metadata": metadata}

    except Exception as e:
        logger.error(f"上传失败: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def merge_raster_bands_task(raster_ids: str, new_name: str, db: AsyncSession) -> dict:
    """查询各波段路径 → 合并 → 转 COG → 注册数据库"""
    ids = [int(i) for i in raster_ids.split(',')]
    input_paths = []

    for rid in ids:
        result = await db.execute(
            select(models.RasterMetadata).where(models.RasterMetadata.index_id == rid)
        )
        r = result.scalars().first()
        if r:
            input_paths.append(r.file_path)

    if not input_paths:
        raise HTTPException(status_code=400, detail="未找到有效波段路径")

    upload_id = str(uuid.uuid4())
    tmp_tiff = os.path.join(UPLOAD_DIR, f"{upload_id}_merged.tif")
    cog_filename = (
        f"{upload_id}_{new_name}.tif"
        if not new_name.endswith('.tif')
        else f"{upload_id}_{new_name}"
    )
    cog_output = os.path.join(COG_DIR, cog_filename)

    RasterProcessor.merge_bands(input_paths, tmp_tiff)
    RasterProcessor.convert_to_cog(tmp_tiff, cog_output)

    return await db_ops.save_to_db(
        db, upload_id, new_name, tmp_tiff,
        cog_filename, cog_output, "merged",
        bands_count=len(input_paths)
    )


@router.post("/upload")
async def upload_raster(
        file: UploadFile = File(...),
        bundle_id: str = Form(None),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: AsyncSession = Depends(get_db)
):
    return await save_and_process_file(file, db, background_tasks, bundle_id=bundle_id)


@router.post("/merge-bands")
async def merge_bands(
        raster_ids: str = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await merge_raster_bands_task(raster_ids, new_name, db)
