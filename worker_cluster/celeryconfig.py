"""Celery configuration for the RSMarking worker cluster."""

from __future__ import annotations

import os
import platform

from kombu import Queue


broker_url: str = os.getenv(
    "CELERY_BROKER_URL",
    "amqp://rs_admin:rs_password@localhost:5672/rsmarking_vhost",
)

result_backend: str = os.getenv(
    "CELERY_RESULT_BACKEND",
    "redis://localhost:6379/0",
)

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "Asia/Shanghai"
enable_utc = True
result_expires = 60 * 60 * 24

_is_windows = platform.system() == "Windows"
worker_pool = os.getenv("WORKER_POOL", "solo" if _is_windows else "prefork")
worker_concurrency = int(os.getenv("WORKER_CONCURRENCY", "1" if worker_pool == "solo" else "4"))
worker_prefetch_multiplier = 1
task_acks_late = True
task_reject_on_worker_lost = True

task_soft_time_limit = int(os.getenv("TASK_SOFT_LIMIT", str(60 * 30)))
task_time_limit = int(os.getenv("TASK_HARD_LIMIT", str(60 * 35)))
task_max_retries = 3
task_default_retry_delay = 10

task_queues = (
    Queue("preprocess"),
    Queue("index"),
    Queue("export"),
    Queue("extraction"),
)
task_routes = {
    "worker_cluster.tasks.preprocess.*": {"queue": "preprocess"},
    "worker_cluster.tasks.index.*": {"queue": "index"},
    "worker_cluster.tasks.algorithm.*": {"queue": "index"},
    "worker_cluster.tasks.export.*": {"queue": "export"},
    "worker_cluster.tasks.extraction.*": {"queue": "extraction"},
}
task_default_queue = "preprocess"
task_create_missing_queues = True

worker_send_task_events = True
task_send_sent_event = True
