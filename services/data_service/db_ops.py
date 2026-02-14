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
from services.data_service.crud import RasterCRUD


logger = logging.getLogger("data_service.db_ops")


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")


def run_conversion(input_path: str, output_path: str):
    try:
        RasterProcessor.convert_to_cog(input_path, output_path)
    except Exception as e:
        logger.error(f"COG transform fail: {str(e)}")


async def save_to_db(db: AsyncSession, task_id: str, new_name: str, tmp_path: str, cog_filename: str, cog_path: str,
                     prefix: str, bands_count: int = 1, metadata_source: str = None):
    """
    Common metadata extraction and storage logic
    :param metadata_source: Specifies which file to extract metadata from. If uploading, pass raw_path; if it's a calculation result, pass cog_path.
    """
    # If no metadata source is specified, it will attempt to read from cog_path by default; otherwise, it will read from the specified path.
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


async def process_index_task(db: AsyncSession, band_ids: list, new_name: str, prefix: str, processor_func):
    try:
        paths = []
        for bid in band_ids:
            res = await db.execute(select(models.RasterMetadata).where(models.RasterMetadata.index_id == bid))
            r = res.scalar_one_or_none()
            if not r: raise HTTPException(status_code=404, detail=f"Band index {bid} does not exist")
            paths.append(r.file_path)

        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        
        processor_func(*paths, tmp_path)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)
    except Exception as e:
        logger.error(f"{prefix} calculate fail: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_extraction_task(db: AsyncSession, band_ids: List[int],
                                  new_name: str, prefix: str, processor_func, **kwargs):
    try:
        from . import models
        paths = []
        for bid in band_ids:
            stmt = select(models.RasterMetadata).where(models.RasterMetadata.index_id == bid)
            res = await db.execute(stmt)
            r = res.scalar_one_or_none()
            if not r:
                raise HTTPException(status_code=404, detail=f"Band index {bid} does not exist.")
            paths.append(r.file_path)
        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)
        processor_func(paths, tmp_path, **kwargs)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)
        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)

    except Exception as e:
        logger.error(f"{prefix} Fetch task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))


async def get_dynamic_band_ids(request: Request) -> List[int]:
    form_data = await request.form()
    id_keys = [k for k in form_data.keys() if re.match(r'^id_\d+$', k)]
    id_keys.sort(key=lambda x: int(x.split('_')[1]))
    return [int(form_data[k]) for k in id_keys]
