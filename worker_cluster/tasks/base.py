"""
BaseRasterTask —— 所有栅格任务的基类
─────────────────────────────────────────────────────────────────────────────
职责：
  1. 统一的 before_start / on_failure / on_success 钩子
  2. 自动将状态写入 Redis（通过 StatusReporter）
  3. 提供 self.report(progress, message) 便捷方法
"""
import logging
from celery import Task

from worker_cluster.bridge.status_reporter import set_task_status

logger = logging.getLogger("worker.base_task")


class BaseRasterTask(Task):
    """
    继承此类的任务自动获得：
      - Redis 状态追踪
      - 统一异常日志
      - 重试时状态回退为 running
    用法：
        @app.task(bind=True, base=BaseRasterTask)
        def my_task(self, ...):
            self.report(10, "开始处理")
            ...
            self.report(100, "完成")
    """
    abstract = True

    # ── 钩子 ──────────────────────────────────────────────────────────────────

    def before_start(self, task_id, args, kwargs):
        logger.info(f"[Task:{self.name}] started  id={task_id}")
        set_task_status(task_id, "running", progress=0, message="任务已启动")

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"[Task:{self.name}] success  id={task_id}  retval={retval}")
        set_task_status(
            task_id, "success",
            progress=100,
            message="任务完成",
            result=retval if isinstance(retval, dict) else {"value": retval},
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"[Task:{self.name}] failed   id={task_id}  exc={exc}")
        set_task_status(
            task_id, "failed",
            progress=0,
            message=str(exc),
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"[Task:{self.name}] retrying id={task_id}  exc={exc}")
        set_task_status(
            task_id, "running",
            progress=0,
            message=f"重试中: {exc}",
        )

    # ── 便捷方法 ──────────────────────────────────────────────────────────────

    def report(self, progress: int, message: str = "") -> None:
        """在任务执行中途汇报进度，前端可实时感知"""
        set_task_status(
            self.request.id,
            "running",
            progress=progress,
            message=message,
        )
        # 同时更新 Celery 内置 meta（兼容 AsyncResult.info）
        self.update_state(
            state="PROGRESS",
            meta={"progress": progress, "message": message},
        )