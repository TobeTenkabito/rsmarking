"""
Celery + RabbitMQ 配置
所有配置项均可通过环境变量覆盖
"""
import os

# ── Broker & Backend ──────────────────────────────────────────────────────────
# RabbitMQ 作为消息队列
broker_url: str = os.getenv(
    "CELERY_BROKER_URL",
    "amqp://rs_admin:rs_password@localhost:5672/rsmarking_vhost",
)

# Redis 作为结果后端（轻量，仅存状态+少量元数据）
result_backend: str = os.getenv(
    "CELERY_RESULT_BACKEND",
    "redis://localhost:6379/0",
)

# ── 序列化 ────────────────────────────────────────────────────────────────────
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "Asia/Shanghai"
enable_utc = True

# ── 结果保留时间 ───────────────────────────────────────────────────────────────
result_expires = 60 * 60 * 24  # 24 小时后 Redis 自动清除

# ── 并发 & 预取 ───────────────────────────────────────────────────────────────
# IO 密集型（栅格读写）用 prefork，CPU 密集型可换 gevent
worker_concurrency = int(os.getenv("WORKER_CONCURRENCY", "4"))
worker_prefetch_multiplier = 1          # 每次只预取 1 个任务，避免大任务饿死
task_acks_late = True           # 任务执行完毕再 ACK，崩溃后自动重投
task_reject_on_worker_lost = True       # Worker 意外退出时拒绝任务，触发重投

# ── 超时 ──────────────────────────────────────────────────────────────────────
task_soft_time_limit = int(os.getenv("TASK_SOFT_LIMIT", str(60 * 30)))   # 30 min 软超时 → SoftTimeLimitExceeded
task_time_limit = int(os.getenv("TASK_HARD_LIMIT", str(60 * 35)))   # 35 min 硬超时 → SIGKILL

# ── 重试策略（默认，各任务可覆盖）────────────────────────────────────────────
task_max_retries = 3
task_default_retry_delay = 10           # 秒

# ── 队列路由 ──────────────────────────────────────────────────────────────────
# 预处理任务走 preprocess 队列；导出任务走 export 队列
# 启动时分别指定 -Q preprocess 或 -Q export 可实现资源隔离
task_routes = {
    "worker_cluster.tasks.preprocess.*": {"queue": "preprocess"},
    "worker_cluster.tasks.export.*":     {"queue": "export"},
}

task_default_queue = "preprocess"

# ── 监控（Flower 可直接消费） ─────────────────────────────────────────────────
worker_send_task_events = True
task_send_sent_event = True
