import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.bridges.worker_bridge import get_cluster_task_status
from services.data_service.database import get_db


logger = logging.getLogger("data_service.tasks")
router = APIRouter(tags=["Tasks"])


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    status = get_cluster_task_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task status not found")
    return status


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text(
            """
            SELECT job_id, celery_task_id, task_type, status, raster_index_id,
                   params, result, error, retry_count, created_at, started_at, finished_at
            FROM task_jobs
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    payload = {key: _jsonable(value) for key, value in row.items()}
    task_id = payload.get("celery_task_id")
    if task_id:
        payload["task_status"] = get_cluster_task_status(task_id)
    return payload

