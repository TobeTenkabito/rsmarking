"""Bridge from data_service routes to the Celery compute cluster."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any


logger = logging.getLogger("data_service.worker_bridge")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")

RASTER_PRODUCT_TASK = "worker_cluster.tasks.algorithm.raster_product"
WORKER_PING_TIMEOUT = float(os.getenv("RS_CLUSTER_PING_TIMEOUT", "1.0"))


class ClusterDispatchError(RuntimeError):
    """Raised when a job cannot be submitted to the compute cluster."""


def cluster_enabled() -> bool:
    backend = os.getenv("RS_PROCESSING_BACKEND", "cluster").strip().lower()
    return backend in {"cluster", "celery", "worker", "async"}


def cluster_fallback_enabled() -> bool:
    value = os.getenv("RS_CLUSTER_FALLBACK", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def require_live_worker() -> bool:
    value = os.getenv("RS_CLUSTER_REQUIRE_WORKER", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def build_output_paths(prefix: str) -> dict[str, str]:
    output_id = uuid.uuid4().hex
    raw_path = os.path.join(UPLOAD_DIR, f"{output_id}_{prefix}_raw.tif")
    cog_filename = f"{output_id}_{prefix}.tif"
    cog_path = os.path.join(COG_DIR, cog_filename)
    return {
        "output_id": output_id,
        "raw_path": raw_path,
        "cog_filename": cog_filename,
        "cog_path": cog_path,
        "cog_public_path": f"/data/{cog_filename}",
    }


def _task_type(operation: str, prefix: str) -> str:
    if operation in {"ndvi", "ndwi", "ndbi", "mndwi"}:
        return "calc_index"
    if operation == "calculator":
        return "calc_custom"
    if operation in {"vegetation", "water", "building", "cloud"}:
        return "extract_feature"
    if operation == "clip_raster_by_vector":
        return "clip_raster"
    if operation in {"merge_bands", "extract_bands"}:
        return prefix
    if operation == "resample":
        return "resample_raster"
    return operation


def _queue_has_live_worker(celery_app, queue: str, task_name: str) -> bool:
    inspector = celery_app.control.inspect(timeout=WORKER_PING_TIMEOUT)
    active_queues = inspector.active_queues()
    if active_queues:
        queue_workers = [
            worker_name
            for worker_name, queues in active_queues.items()
            if any(item.get("name") == queue for item in queues or [])
        ]
        if not queue_workers:
            return False

        registered = inspector.registered() or {}
        if registered:
            return any(task_name in registered.get(worker_name, []) for worker_name in queue_workers)
        return True

    # Some transports do not answer active_queues reliably; ping is still
    # enough to prove a worker is alive for the default routing setup.
    ping = inspector.ping() or {}
    return bool(ping)


def submit_raster_product_job(
    *,
    operation: str,
    inputs: dict[str, Any],
    new_name: str,
    prefix: str,
    params: dict[str, Any] | None = None,
    raster_index_id: int | str | None = None,
    queue: str = "index",
    bundle_id: str | None = None,
) -> dict[str, Any]:
    """Submit a raster product job to the compute cluster."""

    output = build_output_paths(prefix)
    registration = {
        "new_name": new_name,
        "prefix": prefix,
        "output_id": output["output_id"],
        "bundle_id": bundle_id,
    }
    kwargs = {
        "operation": operation,
        "inputs": inputs,
        "output": {
            "raw_path": output["raw_path"],
            "cog_path": output["cog_path"],
            "cog_public_path": output["cog_public_path"],
        },
        "registration": registration,
        "params": params or {},
    }

    try:
        from worker_cluster.app import celery_app
        from worker_cluster.producer import submit_task

        if require_live_worker() and not _queue_has_live_worker(celery_app, queue, RASTER_PRODUCT_TASK):
            raise ClusterDispatchError(
                f"No ready Celery worker is consuming '{queue}' with task "
                f"'{RASTER_PRODUCT_TASK}'. Start or restart worker_cluster, "
                "or set RS_PROCESSING_BACKEND=inline."
            )

        submission = submit_task(
            RASTER_PRODUCT_TASK,
            task_type=_task_type(operation, prefix),
            kwargs=kwargs,
            queue=queue,
            raster_index_id=raster_index_id,
            create_job_record=True,
        )
    except ClusterDispatchError:
        raise
    except Exception as exc:
        logger.warning("Cluster dispatch failed for %s: %s", operation, exc)
        raise ClusterDispatchError(str(exc)) from exc

    return {
        "status": "accepted",
        "execution": "cluster",
        "operation": operation,
        "job_id": submission.get("job_id"),
        "task_id": submission["task_id"],
        "queue": submission.get("queue") or queue,
        "job_recorded": submission.get("job_recorded", False),
        "status_url": f"/tasks/{submission['task_id']}/status",
        "job_url": f"/jobs/{submission['job_id']}" if submission.get("job_id") else None,
        "output": {
            "raw_path": output["raw_path"],
            "cog_path": output["cog_public_path"],
        },
    }


def get_cluster_task_status(task_id: str) -> dict[str, Any] | None:
    redis_status = None
    try:
        from worker_cluster.bridge.status_reporter import get_task_status

        redis_status = get_task_status(task_id)
    except Exception as exc:
        logger.warning("Cluster status lookup failed for %s: %s", task_id, exc)

    try:
        from celery.result import AsyncResult
        from worker_cluster.app import celery_app

        result = AsyncResult(task_id, app=celery_app)
        state = (result.state or "").lower()

        if state == "success":
            payload = result.result if isinstance(result.result, dict) else {"value": result.result}
            return {
                "task_id": task_id,
                "status": "success",
                "progress": 100,
                "message": "Task completed",
                "result": payload,
            }

        if state in {"failure", "revoked"}:
            return {
                "task_id": task_id,
                "status": "failed" if state == "failure" else "revoked",
                "progress": 0,
                "message": str(result.info or result.result or state),
                "result": {},
            }

        if state == "retry":
            return {
                "task_id": task_id,
                "status": "retrying",
                "progress": redis_status.get("progress", 0) if redis_status else 0,
                "message": str(result.info or "Task retrying"),
                "result": {},
            }
    except Exception as exc:
        logger.warning("Celery result lookup failed for %s: %s", task_id, exc)

    return redis_status
