"""Helpers for submitting worker_cluster tasks."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from worker_cluster.app import celery_app
from worker_cluster.bridge.db_sync import get_sync_db
from worker_cluster.bridge.status_reporter import report_failure, set_task_status
from worker_cluster.models import TaskJob, TaskStatus

logger = logging.getLogger("worker.producer")


def _infer_queue(task_name: str) -> str | None:
    if ".preprocess." in task_name:
        return "preprocess"
    if ".index." in task_name:
        return "index"
    if ".export." in task_name:
        return "export"
    if ".extraction." in task_name:
        return "extraction"
    return None


def _create_job_record(
    job_id: str,
    task_type: str,
    raster_index_id: str | int | None,
    params: dict[str, Any],
) -> bool:
    try:
        with get_sync_db() as db:
            db.add(
                TaskJob(
                    job_id=job_id,
                    task_type=task_type,
                    status=TaskStatus.PENDING.value,
                    raster_index_id=str(raster_index_id) if raster_index_id is not None else None,
                    params=params,
                )
            )
        return True
    except Exception as exc:
        logger.warning("TaskJob persistence unavailable for %s: %s", job_id, exc)
        return False


def _attach_celery_task_id(job_id: str, celery_task_id: str) -> None:
    try:
        with get_sync_db() as db:
            job = db.query(TaskJob).filter(TaskJob.job_id == job_id).first()
            if job is not None:
                job.celery_task_id = celery_task_id
    except Exception as exc:
        logger.warning("Failed to attach celery_task_id for %s: %s", job_id, exc)


def submit_task(
    task_name: str,
    *,
    task_type: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    queue: str | None = None,
    raster_index_id: str | int | None = None,
    create_job_record: bool = True,
) -> dict[str, Any]:
    """Submit a Celery task and optionally create a `task_jobs` record."""

    args = args or []
    kwargs = kwargs or {}
    queue = queue or _infer_queue(task_name)
    job_id = uuid.uuid4().hex
    recorded = False

    if create_job_record:
        recorded = _create_job_record(
            job_id=job_id,
            task_type=task_type,
            raster_index_id=raster_index_id,
            params={"args": args, "kwargs": kwargs},
        )

    send_options: dict[str, Any] = {}
    if recorded:
        send_options["headers"] = {"job_id": job_id}
    if queue:
        send_options["queue"] = queue

    try:
        async_result = celery_app.send_task(task_name, args=args, kwargs=kwargs, **send_options)
    except Exception as exc:
        if recorded:
            report_failure(job_id, f"Task submission failed: {exc}")
        raise

    set_task_status(async_result.id, "pending", progress=0, message="Task submitted")

    if recorded:
        _attach_celery_task_id(job_id, async_result.id)

    return {
        "job_id": job_id if recorded else None,
        "task_id": async_result.id,
        "queue": queue,
        "job_recorded": recorded,
    }
