import os
import uuid
import logging
import re
from fastapi import HTTPException, Request
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from functions.common.snowflake_utils import get_next_index_id
import services.data_service.models as models
from services.data_service.processor import RasterProcessor
from services.data_service.crud.raster_crud import RasterCRUD

logger = logging.getLogger("data_service.db_ops")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")


def run_conversion(input_path: str, output_path: str):
    try:
        RasterProcessor.convert_to_cog(input_path, output_path)
    except Exception as e:
        logger.error(f"COG 转换失败: {str(e)}")


async def save_to_db(
    db: AsyncSession,
    task_id: str,
    new_name: str,
    tmp_path: str,
    cog_filename: str,
    cog_path: str,
    prefix: str,
    bands_count: int = 1,
    metadata_source: str = None
):
    source_for_meta = metadata_source if metadata_source else cog_path
    metadata = RasterProcessor.extract_metadata(source_for_meta)

    db_data = {
        "file_name": new_name if new_name.endswith(".tif") else f"{new_name}.tif",
        "file_path": tmp_path,
        "cog_path": f"/data/{cog_filename}",
        "bundle_id": f"{prefix}_{task_id[:8]}",
        "index_id": get_next_index_id(),
        "crs": metadata.get("crs"),
        "bounds": metadata.get("bounds"),
        "center": metadata.get("center"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "bands": bands_count,
        "data_type": metadata.get("data_type"),
        "resolution_x": metadata.get("resolution")[0] if metadata.get("resolution") else None,
        "resolution_y": metadata.get("resolution")[1] if metadata.get("resolution") else None
    }

    new_record = await RasterCRUD.create_raster(db, db_data)
    await db.commit()

    return {"status": "success", "id": new_record.id, "cog_url": db_data["cog_path"]}


async def _get_band_paths(db: AsyncSession, band_ids: List[int]) -> List[str]:
    """
    批量获取 band path
    """
    stmt = select(models.RasterMetadata).where(
        models.RasterMetadata.index_id.in_(band_ids)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    if len(records) != len(band_ids):
        raise HTTPException(status_code=404, detail="部分波段ID不存在")
    record_map = {r.index_id: r for r in records}
    return [record_map[i].file_path for i in band_ids]


async def process_index_task(db: AsyncSession, band_ids: list, new_name: str, prefix: str, processor_func):
    try:

        paths = await _get_band_paths(db, band_ids)
        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)
        processor_func(*paths, tmp_path)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)
        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)

    except Exception as e:
        logger.error(f"{prefix} 计算失败: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_extraction_task(db: AsyncSession, band_ids: List[int], new_name: str, prefix: str, processor_func, **kwargs):
    try:
        paths = await _get_band_paths(db, band_ids)
        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)
        processor_func(paths, tmp_path, **kwargs)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)
        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)

    except Exception as e:
        logger.error(f"{prefix} 提取任务失败: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_calculator_task(
        db: AsyncSession,
        var_mapping: dict[str, int],
        expression: str,
        new_name: str,
        prefix: str
):
    try:
        # 获取所有相关 raster_id 的路径
        raster_ids = list(var_mapping.values())
        paths = await _get_band_paths(db, raster_ids)

        # 将 var_name -> raster_id 转换为 var_name -> file_path
        path_mapping = {
            var_name: paths[raster_ids.index(r_id)]
            for var_name, r_id in var_mapping.items()
        }

        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        RasterProcessor.run_raster_calculator(path_mapping, expression, tmp_path)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)

    except Exception as e:
        logger.error(f"栅格计算器任务失败: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def get_dynamic_band_ids(request: Request) -> List[int]:
    form_data = await request.form()
    id_keys = [
        k for k in form_data.keys()
        if re.match(r'^id_\d+$', k)]
    id_keys.sort(key=lambda x: int(x.split('_')[1]))
    return [int(form_data[k]) for k in id_keys]
