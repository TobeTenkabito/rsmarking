"""
光谱指数计算任务
─────────────────────────────────────────────────────────────────────────────
将 RasterProcessor 中的同步计算包装为 Celery 异步任务，
支持 NDVI / NDWI / NDBI / MNDWI 及自定义栅格计算器。
"""
import logging
import os

from worker_cluster.app import celery_app
from worker_cluster.tasks.base import BaseRasterTask
from services.data_service.processor import RasterProcessor

logger = logging.getLogger("worker.spectral")


@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.index.ndvi",
    queue="index",
)
def ndvi_task(self, red_path: str, nir_path: str, output_path: str) -> dict:
    """计算 NDVI = (NIR - Red) / (NIR + Red)"""
    try:
        self.report(20, "计算 NDVI")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
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
    """计算 NDWI = (Green - NIR) / (Green + NIR)"""
    try:
        self.report(20, "计算 NDWI")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
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
    """计算 NDBI = (SWIR - NIR) / (SWIR + NIR)"""
    try:
        self.report(20, "计算 NDBI")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
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
    """计算 MNDWI = (Green - SWIR) / (Green + SWIR)"""
    try:
        self.report(20, "计算 MNDWI")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
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
    """
    自定义栅格计算器（numexpr 表达式）

    Args:
        path_mapping : {"A": "/path/a.tif", "B": "/path/b.tif"}
        expression   : "(A - B) / (A + B)"
        output_path  : 结果路径
    """
    try:
        self.report(20, f"执行表达式: {expression}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        RasterProcessor.run_raster_calculator(path_mapping, expression, output_path)
        return {"output_path": output_path, "expression": expression}
    except Exception as exc:
        logger.exception("[calculator_task] failed")
        raise self.retry(exc=exc, countdown=10)
