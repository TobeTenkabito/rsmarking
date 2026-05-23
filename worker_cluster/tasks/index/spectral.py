"""Celery tasks for spectral indices and raster calculator jobs."""

from __future__ import annotations

import logging
import os

from services.data_service.processor import RasterProcessor
from worker_cluster.app import celery_app
from worker_cluster.tasks.base import BaseRasterTask


logger = logging.getLogger("worker.spectral")


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.index.ndvi",
    queue="index",
)
def ndvi_task(self, red_path: str, nir_path: str, output_path: str) -> dict:
    try:
        self.report(20, "Calculating NDVI")
        _ensure_parent_dir(output_path)
        RasterProcessor.calculate_ndvi(red_path, nir_path, output_path)
        return {"output_path": output_path, "index": "NDVI"}
    except Exception as exc:
        logger.exception("[ndvi_task] failed")
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.index.ndwi",
    queue="index",
)
def ndwi_task(self, green_path: str, nir_path: str, output_path: str) -> dict:
    try:
        self.report(20, "Calculating NDWI")
        _ensure_parent_dir(output_path)
        RasterProcessor.calculate_ndwi(green_path, nir_path, output_path)
        return {"output_path": output_path, "index": "NDWI"}
    except Exception as exc:
        logger.exception("[ndwi_task] failed")
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.index.ndbi",
    queue="index",
)
def ndbi_task(self, swir_path: str, nir_path: str, output_path: str) -> dict:
    try:
        self.report(20, "Calculating NDBI")
        _ensure_parent_dir(output_path)
        RasterProcessor.calculate_ndbi(swir_path, nir_path, output_path)
        return {"output_path": output_path, "index": "NDBI"}
    except Exception as exc:
        logger.exception("[ndbi_task] failed")
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.index.mndwi",
    queue="index",
)
def mndwi_task(self, green_path: str, swir_path: str, output_path: str) -> dict:
    try:
        self.report(20, "Calculating MNDWI")
        _ensure_parent_dir(output_path)
        RasterProcessor.calculate_mndwi(green_path, swir_path, output_path)
        return {"output_path": output_path, "index": "MNDWI"}
    except Exception as exc:
        logger.exception("[mndwi_task] failed")
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.index.calculator",
    queue="index",
)
def calculator_task(
    self,
    path_mapping: dict[str, str],
    expression: str,
    output_path: str,
) -> dict:
    try:
        self.report(20, f"Running expression: {expression}")
        _ensure_parent_dir(output_path)
        RasterProcessor.run_raster_calculator(path_mapping, expression, output_path)
        return {"output_path": output_path, "expression": expression}
    except Exception as exc:
        logger.exception("[calculator_task] failed")
        raise self.retry(exc=exc, countdown=10)
