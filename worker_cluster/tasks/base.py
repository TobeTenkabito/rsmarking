"""Shared base task with status tracking helpers."""

from __future__ import annotations

import logging

from celery import Task

from worker_cluster.bridge.status_reporter import (
    report_failure,
    report_retry,
    report_running,
    report_success,
    set_task_status,
)

logger = logging.getLogger("worker.base_task")


class BaseRasterTask(Task):
    """Base class for long-running worker tasks.

    Features:
    - consistent logging for task lifecycle events
    - progress/status writes to Redis via ``set_task_status``
    - optional ``task_jobs`` persistence when a producer sends ``job_id`` in
      Celery headers
    """

    abstract = True

    def _get_job_id(self) -> str | None:
        headers = getattr(self.request, "headers", None) or {}
        return headers.get("job_id")

    def before_start(self, task_id, args, kwargs):
        logger.info("[Task:%s] started id=%s", self.name, task_id)
        set_task_status(task_id, "running", progress=0, message="Task started")

        job_id = self._get_job_id()
        if job_id:
            report_running(job_id, task_id)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info("[Task:%s] success id=%s retval=%s", self.name, task_id, retval)
        result_payload = retval if isinstance(retval, dict) else {"value": retval}
        set_task_status(
            task_id,
            "success",
            progress=100,
            message="Task completed",
            result=result_payload,
        )

        job_id = self._get_job_id()
        if job_id:
            report_success(job_id, result_payload)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("[Task:%s] failed id=%s exc=%s", self.name, task_id, exc)
        set_task_status(
            task_id,
            "failed",
            progress=0,
            message=str(exc),
        )

        job_id = self._get_job_id()
        if job_id:
            report_failure(job_id, str(exc))

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning("[Task:%s] retrying id=%s exc=%s", self.name, task_id, exc)
        retry_count = int(getattr(self.request, "retries", 0)) + 1
        set_task_status(
            task_id,
            "running",
            progress=0,
            message=f"Retrying: {exc}",
        )

        job_id = self._get_job_id()
        if job_id:
            report_retry(job_id, str(exc), retry_count)

    def report(self, progress: int, message: str = "") -> None:
        """Write in-flight progress updates to Redis and Celery state."""
        set_task_status(
            self.request.id,
            "running",
            progress=progress,
            message=message,
        )
        self.update_state(
            state="PROGRESS",
            meta={"progress": progress, "message": message},
        )
