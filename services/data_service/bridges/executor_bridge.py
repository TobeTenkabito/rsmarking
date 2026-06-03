import logging
import os
import re
import uuid

import httpx
import rasterio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.db_ops import COG_DIR, UPLOAD_DIR, save_to_db
from services.data_service.processor import RasterProcessor

logger = logging.getLogger("data_service.executor_bridge")

EXECUTOR_URL = os.getenv("EXECUTOR_SERVICE_URL", "http://localhost:8004/execute")
MAX_EXECUTOR_LOG_LINES = 40
MAX_EXECUTOR_LOG_CHARS = 4000


def _sandbox_raster_alias(raster_id: int) -> str:
    token = re.sub(r"\W+", "_", str(raster_id)).strip("_") or "input"
    return f"raster_{token}"


def _trim_executor_logs(logs: str) -> str:
    lines = [line for line in logs.splitlines() if line.strip()]
    excerpt = "\n".join(lines[-MAX_EXECUTOR_LOG_LINES:])
    if len(excerpt) <= MAX_EXECUTOR_LOG_CHARS:
        return excerpt
    return excerpt[-MAX_EXECUTOR_LOG_CHARS:]


def _format_executor_error(res_data: dict) -> str:
    message = str(
        res_data.get("error")
        or res_data.get("message")
        or "Sandbox execution failed"
    )
    logs = _trim_executor_logs(str(res_data.get("logs") or ""))
    if logs and logs not in message:
        return f"{message}\n{logs}"
    return message


def _resolve_executor_input_path(raster) -> str:
    candidates = [raster.file_path, raster.cog_path]

    for path in candidates:
        if path and os.path.exists(path):
            return path

        if path and path.startswith("/data/"):
            local_candidate = os.path.join(COG_DIR, os.path.basename(path))
            if os.path.exists(local_candidate):
                return local_candidate

    raise HTTPException(
        status_code=404,
        detail=(
            f"Raster file is missing on disk for index_id={raster.index_id}. "
            f"file_path={raster.file_path}, cog_path={raster.cog_path}"
        ),
    )


async def dispatch_user_script(
    db: AsyncSession,
    script: str,
    raster_ids: list[int],
    output_name: str,
):
    input_files_payload = []
    for raster_id in raster_ids:
        raster = await RasterCRUD.get_raster_by_index_id(db, raster_id)
        if not raster:
            raise HTTPException(status_code=404, detail=f"Raster ID {raster_id} was not found")

        resolved_path = _resolve_executor_input_path(raster)
        input_files_payload.append({
            "path": resolved_path,
            "name": os.path.basename(resolved_path),
            "raster_id": raster_id,
            "alias": _sandbox_raster_alias(raster_id),
        })

    task_id = str(uuid.uuid4())
    prefix = "script"
    raw_output_filename = f"{task_id}_{prefix}_raw.tif"

    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            payload = {
                "script_id": task_id,
                "script": script,
                "input_files": input_files_payload,
                "output_name": raw_output_filename,
            }
            response = await client.post(EXECUTOR_URL, json=payload)
            response.raise_for_status()
            res_data = response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Executor service is unavailable")
        except httpx.HTTPStatusError as e:
            detail = e.response.text if e.response is not None else str(e)
            logger.error("Executor service returned an HTTP error: %s", detail)
            raise HTTPException(status_code=502, detail=f"Executor service error: {detail}")
        except Exception as e:
            logger.error("Executor service call failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Executor dispatch failed: {e}")

    if res_data.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=_format_executor_error(res_data),
        )

    tmp_path = res_data.get("output_path") or os.path.join(UPLOAD_DIR, raw_output_filename)
    cog_filename = f"{task_id}_{prefix}.tif"
    cog_path = os.path.join(COG_DIR, cog_filename)

    if not os.path.exists(tmp_path):
        raise HTTPException(status_code=500, detail="Executor did not produce the output raster")

    try:
        RasterProcessor.convert_to_cog(tmp_path, cog_path)
        with rasterio.open(tmp_path) as src:
            actual_bands = src.count

        db_res = await save_to_db(
            db=db,
            task_id=task_id,
            new_name=output_name,
            tmp_path=tmp_path,
            cog_filename=cog_filename,
            cog_path=cog_path,
            prefix=prefix,
            bands_count=actual_bands,
        )

        return {
            "status": "success",
            "id": db_res.get("id"),
            "cog_url": db_res.get("cog_url"),
            "logs": res_data.get("logs", ""),
        }
    except Exception as e:
        logger.error("Script result post-processing failed: %s", e)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Failed to persist executor output: {e}")
