"""
preprocesstask
─────────────────────────────────────────────────────────────────────────────
text:
  - build_cog_task        : text -> COG + text,text cog_path
  - build_overviews_task  : textBuilding overviews(text COG whenuses)
  - reproject_task        : reproject to CRS
  - compute_statistics_task: text(min/max/mean/std),write RasterField
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


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)

# ─── 1. COG conversion + text ─────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.preprocess.build_cog",
    queue="preprocess",
    max_retries=2,
)
def build_cog_task(self, index_id: int, raw_path: str, cog_path: str) -> dict:
    """
    imageryconvert to COG textBuilding overviews,text cog_path database.

    Args:
        index_id : RasterMetadata.index_id(text ID)
        raw_path : path
        cog_path : text COG path
    Returns:
        {"index_id": ..., "cog_path": ...}
    """
    try:
        self.report(10, "Starting COG conversion")
        _ensure_parent_dir(cog_path)

        self.report(30, "Converting...")
        RasterProcessor.convert_to_cog(raw_path, cog_path)

        self.report(70, "Building overviews")
        build_raster_overviews(cog_path)

        self.report(90, "Writing back to database")
        update_cog_path(index_id, cog_path)

        logger.info(f"[build_cog] done index_id={index_id}")
        return {"index_id": index_id, "cog_path": cog_path}

    except Exception as exc:
        logger.exception(f"[build_cog] failed index_id={index_id}")
        raise self.retry(exc=exc, countdown=15)


# ─── 2. textBuilding overviews ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.preprocess.build_overviews",
    queue="preprocess",
)
def build_overviews_task(self, file_path: str) -> dict:
    """
    text COG / GeoTIFF text.

    Args:
        file_path: path
    """
    try:
        self.report(20, "Building overviewstext")
        build_raster_overviews(file_path)
        return {"file_path": file_path, "status": "ok"}
    except Exception as exc:
        logger.exception(f"[build_overviews] failed path={file_path}")
        raise self.retry(exc=exc, countdown=10)


# ─── 3. text ────────────────────────────────────────────────────────────────

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
    reproject tocoordinates,text.

    Args:
        index_id   : RasterMetadata.index_id
        input_path : file path
        output_path: file path
        target_crs : text CRS,text EPSG:4326
    """
    from rasterio.warp import calculate_default_transform, reproject, Resampling

    try:
        self.report(10, f"text -> {target_crs}")
        _ensure_parent_dir(output_path)

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
            self.report(30, "Writing reprojected result")
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

        self.report(80, "Building overviews")
        build_raster_overviews(output_path)

        # text CRS
        self.report(95, "Writing metadata back")
        with get_sync_db() as db:
            row = db.query(RasterMetadata).filter(
                RasterMetadata.index_id == index_id
            ).first()
            if row:
                row.crs = target_crs
                row.cog_path = output_path
            else:
                raise RuntimeError(f"RasterMetadata not found: index_id={index_id}")

        return {"index_id": index_id, "output_path": output_path, "crs": target_crs}

    except Exception as exc:
        logger.exception(f"[reproject] failed index_id={index_id}")
        raise self.retry(exc=exc, countdown=15)


# ─── 4. text ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.preprocess.compute_statistics",
    queue="preprocess",
)
def compute_statistics_task(self, index_id: int, file_path: str) -> dict:
    """
    text min/max/mean/std,resultwrite RasterField table.

    Args:
        index_id  : RasterMetadata.index_id
        file_path : COG file path
    Returns:
        {"index_id": ..., "bands": [{"band": 1, "min": ..., ...}, ...]}
    """
    try:
        self.report(10, "Reading imagery statistics")
        stats_list = []

        with rasterio.open(file_path) as src:
            band_count = src.count
            nodata = src.nodata

            for i in range(1, band_count + 1):
                self.report(
                    10 + int(80 * i / band_count),
                    f"Calculating statistics for band {i}/{band_count}"
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

        # write RasterField(text,cannot be deleted by frontend)
        self.report(92, "Writing statistics fields")
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
