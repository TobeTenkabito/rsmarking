"""
预处理任务集
─────────────────────────────────────────────────────────────────────────────
包含：
  - build_cog_task        : 原始文件 → COG + 金字塔，回写 cog_path
  - build_overviews_task  : 仅构建金字塔（已有 COG 时使用）
  - reproject_task        : 重投影到目标 CRS
  - compute_statistics_task: 计算波段统计（min/max/mean/std），写入 RasterField
"""
import logging
import os

from worker_cluster.app import celery_app
from worker_cluster.tasks.base import BaseRasterTask
from worker_cluster.bridge.status_reporter import update_cog_path
from worker_cluster.bridge.db_sync import get_sync_db

from services.data_service.models import RasterMetadata, RasterField
from services.data_service.processor import RasterProcessor
from functions.implement.io_ops import build_raster_overviews, convert_raster_to_cog

import rasterio
import numpy as np

logger = logging.getLogger("worker.preprocess")

# ─── 1. COG 转换 + 金字塔 ─────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.preprocess.build_cog",
    queue="preprocess",
    max_retries=2,
)
def build_cog_task(self, index_id: int, raw_path: str, cog_path: str) -> dict:
    """
    将原始影像转换为 COG 并构建金字塔，完成后回写 cog_path 到数据库。

    Args:
        index_id : RasterMetadata.index_id（雪花 ID）
        raw_path : 原始文件绝对路径
        cog_path : 输出 COG 绝对路径
    Returns:
        {"index_id": ..., "cog_path": ...}
    """
    try:
        self.report(10, "开始 COG 转换")
        os.makedirs(os.path.dirname(cog_path), exist_ok=True)

        self.report(30, "转换中...")
        RasterProcessor.convert_to_cog(raw_path, cog_path)

        self.report(70, "构建金字塔")
        build_raster_overviews(cog_path)

        self.report(90, "回写数据库")
        update_cog_path(index_id, cog_path)

        logger.info(f"[build_cog] done index_id={index_id}")
        return {"index_id": index_id, "cog_path": cog_path}

    except Exception as exc:
        logger.exception(f"[build_cog] failed index_id={index_id}")
        raise self.retry(exc=exc, countdown=15)


# ─── 2. 仅构建金字塔 ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.preprocess.build_overviews",
    queue="preprocess",
)
def build_overviews_task(self, file_path: str) -> dict:
    """
    对已存在的 COG / GeoTIFF 补建金字塔。

    Args:
        file_path: 目标文件绝对路径
    """
    try:
        self.report(20, "构建金字塔中")
        build_raster_overviews(file_path)
        return {"file_path": file_path, "status": "ok"}
    except Exception as exc:
        logger.exception(f"[build_overviews] failed path={file_path}")
        raise self.retry(exc=exc, countdown=10)


# ─── 3. 重投影 ────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.preprocess.reproject",
    queue="preprocess",
    max_retries=2,
)
def reproject_task(
    self,
    index_id: int,
    input_path: str,
    output_path: str,
    target_crs: str = "EPSG:4326",
) -> dict:
    """
    将栅格重投影到目标坐标系，完成后更新元数据。

    Args:
        index_id   : RasterMetadata.index_id
        input_path : 输入文件路径
        output_path: 输出文件路径
        target_crs : 目标 CRS，默认 EPSG:4326
    """
    from rasterio.warp import calculate_default_transform, reproject, Resampling

    try:
        self.report(10, f"重投影 → {target_crs}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with rasterio.open(input_path) as src:
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds
            )
            meta = src.meta.copy()
            meta.update({
                "crs": target_crs,
                "transform": transform,
                "width": width,
                "height": height,
                "driver": "GTiff",
            })
            self.report(30, "写出重投影结果")
            with rasterio.open(output_path, "w", **meta) as dst:
                for band_idx in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band_idx),
                        destination=rasterio.band(dst, band_idx),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=target_crs,
                        resampling=Resampling.nearest,
                    )

        self.report(80, "构建金字塔")
        build_raster_overviews(output_path)

        # 更新元数据中的 CRS
        self.report(95, "回写元数据")
        with get_sync_db() as db:
            row = db.query(RasterMetadata).filter(
                RasterMetadata.index_id == index_id
            ).first()
            if row:
                row.crs = target_crs
                row.cog_path = output_path

        return {"index_id": index_id, "output_path": output_path, "crs": target_crs}

    except Exception as exc:
        logger.exception(f"[reproject] failed index_id={index_id}")
        raise self.retry(exc=exc, countdown=15)


# ─── 4. 波段统计计算 ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.preprocess.compute_statistics",
    queue="preprocess",
)
def compute_statistics_task(self, index_id: int, file_path: str) -> dict:
    """
    计算每个波段的 min/max/mean/std，结果以系统字段写入 RasterField 表。

    Args:
        index_id  : RasterMetadata.index_id
        file_path : COG 或原始文件路径
    Returns:
        {"index_id": ..., "bands": [{"band": 1, "min": ..., ...}, ...]}
    """
    try:
        self.report(10, "读取影像统计")
        stats_list = []

        with rasterio.open(file_path) as src:
            band_count = src.count
            nodata = src.nodata

            for i in range(1, band_count + 1):
                self.report(
                    10 + int(80 * i / band_count),
                    f"计算波段 {i}/{band_count} 统计"
                )
                data = src.read(i).astype("float32")
                if nodata is not None:
                    data = data[data != nodata]
                if data.size == 0:
                    stats_list.append({"band": i, "min": None, "max": None,
                                       "mean": None, "std": None})
                    continue
                stats_list.append({
                    "band":  i,
                    "min":   float(np.nanmin(data)),
                    "max":   float(np.nanmax(data)),
                    "mean":  float(np.nanmean(data)),
                    "std":   float(np.nanstd(data)),
                })

        # 写入 RasterField（系统字段，前端不可删除）
        self.report(92, "写入统计字段")
        with get_sync_db() as db:
            for s in stats_list:
                band_no = s["band"]
                for stat_key in ("min", "max", "mean", "std"):
                    field_name = f"band{band_no}_{stat_key}"
                    existing = db.query(RasterField).filter(
                        RasterField.raster_index_id == index_id,
                        RasterField.field_name == field_name,
                    ).first()
                    val = s[stat_key]
                    str_val = str(round(val, 6)) if val is not None else None
                    if existing:
                        existing.default_val = str_val
                    else:
                        db.add(RasterField(
                            raster_index_id=index_id,
                            field_name=field_name,
                            field_alias=f"Band{band_no} {stat_key.upper()}",
                            field_type="number",
                            is_system=True,
                            default_val=str_val,
                        ))

        logger.info(f"[compute_statistics] done index_id={index_id}")
        return {"index_id": index_id, "bands": stats_list}

    except Exception as exc:
        logger.exception(f"[compute_statistics] failed index_id={index_id}")
        raise self.retry(exc=exc, countdown=10)
