"""
task status writeback helper(final version)
─────────────────────────────────────────────────────────────────────────────
responsibilities:
  1. Redis  dual write - for fast frontend progress polling
  2. task_jobs table - persist task lifecycle,for admin audit
  3. update_cog_path - write back after preprocessing raster_metadata.cog_path

public functions:
  set_task_status(task_id, status, progress, message, result)  <- BaseRasterTask hook use
  get_task_status(task_id) -> dict | None                      <- route query use
  report_running(job_id, celery_task_id)                       <- when task starts
  report_success(job_id, result_payload)                       <- when task succeeds
  report_failure(job_id, error_msg)                            <- when task fails
  report_retry(job_id, reason, retry_count)                    <- when task retries
  update_cog_path(index_id, cog_path)                          <- write back after preprocessing
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal
import redis
from worker_cluster.bridge.db_sync import get_sync_db

logger = logging.getLogger("worker.status_reporter")
TaskStatus = Literal["pending", "running", "success", "failed", "retrying", "revoked"]
_redis_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
_redis_client = redis.Redis.from_url(_redis_url, decode_responses=True)

_TASK_KEY_PREFIX = "rs:task:"
_TASK_TTL = 60 * 60 * 24


def set_task_status(
    task_id: str,
    status: TaskStatus,
    progress: int = 0,
    message: str = "",
    result: dict | None = None,
) -> None:
    """
    write Redis,through GET /tasks/{task_id}/status polling.
    Redis only log a warning when unavailable,do not block task execution.
    """
    bounded_progress = max(0, min(100, int(progress)))
    payload = {
        "task_id":    task_id,
        "status":     status,
        "progress":   bounded_progress,
        "message":    message,
        "result":     result or {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    key = f"{_TASK_KEY_PREFIX}{task_id}"
    try:
        _redis_client.setex(key, _TASK_TTL, json.dumps(payload, default=str))
    except Exception as e:
        logger.warning(f"[StatusReporter] Redis write failed task_id={task_id}: {e}")


def get_task_status(task_id: str) -> dict | None:
    """from Redis read task status,for route layer queries"""
    key = f"{_TASK_KEY_PREFIX}{task_id}"
    try:
        raw = _redis_client.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning(f"[StatusReporter] Redis read failed task_id={task_id}: {e}")
        return None


def report_running(job_id: str, celery_task_id: str) -> None:
    """taskstarts running:text RUNNING text + record celery_task_id start time"""
    _update_job(
        job_id,
        status="running",
        celery_task_id=celery_task_id,
        started_at=datetime.now(timezone.utc),
    )


def report_success(job_id: str, result_payload: dict[str, Any] | None = None) -> None:
    """task:text SUCCESS + result metadata + completion time"""
    _update_job(
        job_id,
        status="success",
        finished_at=datetime.now(timezone.utc),
        result=result_payload or {},
    )


def report_failure(job_id: str, error_msg: str) -> None:
    """task:text FAILED + error message + completion time"""
    _update_job(
        job_id,
        status="failed",
        finished_at=datetime.now(timezone.utc),
        error=error_msg,
    )


def report_retry(job_id: str, reason: str, retry_count: int) -> None:
    """task:text RETRYING + reason + retry count"""
    _update_job(
        job_id,
        status="retrying",
        error=f"[retry #{retry_count}] {reason}",
        retry_count=retry_count,
    )


def _update_job(job_id: str, status: str, **kwargs) -> None:
    """
    generic task_jobs row update.
    do not raise on write failure,only log,ensure main task is unaffected.
    """
    # deferred import,avoid Worker startup circular dependency
    from worker_cluster.models import TaskJob

    try:
        with get_sync_db() as db:
            job: TaskJob | None = (
                db.query(TaskJob)
                .filter(TaskJob.job_id == job_id)
                .first()
            )
            if job is None:
                logger.warning(
                    f"[StatusReporter] job_id={job_id} does not exist in task_jobs; skipping persistence"
                )
                return
            job.status = status
            for key, val in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, val)
    except Exception as e:
        logger.error(
            f"[StatusReporter] task_jobs writeback failed job_id={job_id}: {e}"
        )


def update_cog_path(index_id: int, cog_path: str) -> None:
    """
    After COG conversion completes, write cog_path back to the raster_metadata table.

    Args:
        index_id : RasterMetadata.index_id(text ID)
        cog_path : text COG path
    Raises:
        RuntimeError: Raise when the matching record is not found so the task retries.
    """
    from services.data_service.models import RasterMetadata

    try:
        with get_sync_db() as db:
            row: RasterMetadata | None = (
                db.query(RasterMetadata)
                .filter(RasterMetadata.index_id == index_id)
                .first()
            )
            if row is None:
                # record,triggertask
                raise RuntimeError(
                    f"RasterMetadata not found: index_id={index_id}"
                )
            row.cog_path = cog_path
            logger.info(
                f"[StatusReporter] cog_path updated: "
                f"index_id={index_id} -> {cog_path}"
            )
    except RuntimeError:
        raise   # propagate upward,let build_cog_task trigger retry
    except Exception as e:
        logger.error(
            f"[StatusReporter] update_cog_path failed index_id={index_id}: {e}"
        )
        raise
