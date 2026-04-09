"""
任务状态回写器（最终版）
─────────────────────────────────────────────────────────────────────────────
职责：
  1. Redis  双写 —— 供前端快速轮询进度
  2. task_jobs 表 —— 持久化任务生命周期，供管理后台审计
  3. update_cog_path —— 预处理完成后回写 raster_metadata.cog_path

对外暴露的函数：
  set_task_status(task_id, status, progress, message, result)  ← BaseRasterTask 钩子用
  get_task_status(task_id) -> dict | None                      ← 路由查询用
  report_running(job_id, celery_task_id)                       ← 任务启动时
  report_success(job_id, result_payload)                       ← 任务成功时
  report_failure(job_id, error_msg)                            ← 任务失败时
  report_retry(job_id, reason, retry_count)                    ← 任务重试时
  update_cog_path(index_id, cog_path)                          ← 预处理完成后回写
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal
import redis
from worker_cluster.bridge.db_sync import get_sync_db

logger = logging.getLogger("worker.status_reporter")
TaskStatus = Literal["pending", "running", "success", "failed", "retrying"]
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
    写入 Redis，前端通过 GET /tasks/{task_id}/status 轮询。
    Redis 不可用时仅记录警告，不阻断任务执行。
    """
    payload = {
        "task_id":    task_id,
        "status":     status,
        "progress":   progress,
        "message":    message,
        "result":     result or {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    key = f"{_TASK_KEY_PREFIX}{task_id}"
    try:
        _redis_client.setex(key, _TASK_TTL, json.dumps(payload))
    except Exception as e:
        logger.warning(f"[StatusReporter] Redis write failed task_id={task_id}: {e}")


def get_task_status(task_id: str) -> dict | None:
    """从 Redis 读取任务状态，供路由层查询"""
    key = f"{_TASK_KEY_PREFIX}{task_id}"
    try:
        raw = _redis_client.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning(f"[StatusReporter] Redis read failed task_id={task_id}: {e}")
        return None


def report_running(job_id: str, celery_task_id: str) -> None:
    """任务开始执行：写 RUNNING 状态 + 记录 celery_task_id 和启动时间"""
    _update_job(
        job_id,
        status="running",
        celery_task_id=celery_task_id,
        started_at=datetime.now(timezone.utc),
    )


def report_success(job_id: str, result_payload: dict[str, Any] | None = None) -> None:
    """任务成功：写 SUCCESS + 结果元数据 + 完成时间"""
    _update_job(
        job_id,
        status="success",
        finished_at=datetime.now(timezone.utc),
        result=result_payload or {},
    )


def report_failure(job_id: str, error_msg: str) -> None:
    """任务失败：写 FAILED + 错误信息 + 完成时间"""
    _update_job(
        job_id,
        status="failed",
        finished_at=datetime.now(timezone.utc),
        error=error_msg,
    )


def report_retry(job_id: str, reason: str, retry_count: int) -> None:
    """任务重试：写 RETRYING + 原因 + 重试次数"""
    _update_job(
        job_id,
        status="retrying",
        error=f"[retry #{retry_count}] {reason}",
        retry_count=retry_count,
    )


def _update_job(job_id: str, status: str, **kwargs) -> None:
    """
    通用 task_jobs 行更新。
    写失败不抛异常，仅记录日志，保证主任务不受影响。
    """
    # 延迟导入，避免 Worker 启动时循环依赖
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
                    f"[StatusReporter] job_id={job_id} 不存在于 task_jobs，跳过持久化"
                )
                return
            job.status = status
            for key, val in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, val)
    except Exception as e:
        logger.error(
            f"[StatusReporter] task_jobs 回写失败 job_id={job_id}: {e}"
        )


def update_cog_path(index_id: int, cog_path: str) -> None:
    """
    COG 转换完成后，将 cog_path 写回 raster_metadata 表。

    Args:
        index_id : RasterMetadata.index_id（雪花 ID）
        cog_path : 生成的 COG 文件绝对路径
    Raises:
        RuntimeError: 找不到对应记录时抛出，触发任务重试
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
                # 找不到记录是严重错误，应触发任务重试
                raise RuntimeError(
                    f"RasterMetadata not found: index_id={index_id}"
                )
            row.cog_path = cog_path
            logger.info(
                f"[StatusReporter] cog_path updated: "
                f"index_id={index_id} → {cog_path}"
            )
    except RuntimeError:
        raise   # 向上传播，让 build_cog_task 触发 retry
    except Exception as e:
        logger.error(
            f"[StatusReporter] update_cog_path failed index_id={index_id}: {e}"
        )
        raise
