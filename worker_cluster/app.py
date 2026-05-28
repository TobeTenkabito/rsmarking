"""Celery application for the worker cluster.

The task modules in this repo live in files such as `pipeline.py` and
`spectral.py`, not in the default `tasks.py` locations that Celery's
autodiscovery expects. We therefore register task modules explicitly so a
worker started from this app reliably loads every task.
"""

from __future__ import annotations

import os
import sys

from celery import Celery

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

TASK_MODULES = (
    "worker_cluster.tasks.preprocess.pipeline",
    "worker_cluster.tasks.index.spectral",
    "worker_cluster.tasks.algorithm.raster_product",
    "worker_cluster.tasks.export.geojson",
)

celery_app = Celery("rsmarking", include=list(TASK_MODULES))
celery_app.config_from_object("worker_cluster.celeryconfig")

existing_imports = tuple(celery_app.conf.imports or ())
celery_app.conf.imports = tuple(dict.fromkeys(existing_imports + TASK_MODULES))

__all__ = ["celery_app", "TASK_MODULES"]
