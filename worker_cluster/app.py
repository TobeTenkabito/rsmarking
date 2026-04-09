"""
Celery App 单例
─────────────────────────────────────────────────────────────────────────────
所有任务模块均从此处导入 celery_app，避免循环依赖。
"""
import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from celery import Celery

celery_app = Celery("rsmarking")
celery_app.config_from_object("worker_cluster.celeryconfig")

# 自动发现所有任务模块
celery_app.autodiscover_tasks([
    "worker_cluster.tasks.preprocess",
    "worker_cluster.tasks.index",
    "worker_cluster.tasks.extraction",
    "worker_cluster.tasks.export",
])