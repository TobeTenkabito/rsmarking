import os
import uuid
import logging
import re
import rasterio
from uuid import UUID
from fastapi import HTTPException, Request
from typing import List, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from rasterio.warp import transform_bounds
from pyproj import CRS
from functions.common.snowflake_utils import get_next_index_id
import services.data_service.models as models
from services.data_service.processor import RasterProcessor
from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.crud.raster_field_crud import RasterFieldCRUD
from services.data_service.bridges import worker_bridge

logger = logging.getLogger("data_service.db_ops")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")


def resolve_raster_record_path(record: models.RasterMetadata) -> str | None:
    candidates = [record.file_path, record.cog_path]
    for path in candidates:
        if not path:
            continue
        if os.path.exists(path):
            return path
        if path.startswith("/data/"):
            local_path = os.path.join(COG_DIR, os.path.basename(path))
            if os.path.exists(local_path):
                return local_path
    return None


def run_conversion(input_path: str, output_path: str):
    try:
        RasterProcessor.convert_to_cog(input_path, output_path)
    except Exception as e:
        logger.error(f"COG 转换失败: {str(e)}")


async def save_to_db(
    db: AsyncSession,
    task_id: str,
    new_name: str,
    tmp_path: str,
    cog_filename: str,
    cog_path: str,
    prefix: str,
    bands_count: int = 1,
    metadata_source: str = None,
    bundle_id: str = None
):
    source_for_meta = metadata_source if metadata_source else cog_path
    metadata = RasterProcessor.extract_metadata(source_for_meta)
    final_bundle_id = bundle_id if bundle_id else f"{prefix}_{task_id[:8]}"
    bounds_wgs84 = None
    try:
        raw_bounds = metadata.get("bounds")
        raw_crs = metadata.get("crs")
        if raw_bounds and raw_crs:
            src_crs = CRS.from_user_input(raw_crs)
            if not src_crs.equals(CRS.from_epsg(4326)):
                west, south, east, north = transform_bounds(
                    src_crs, "EPSG:4326",
                    raw_bounds[0], raw_bounds[1],
                    raw_bounds[2], raw_bounds[3]
                )
            else:
                west, south, east, north = raw_bounds
            bounds_wgs84 = [west, south, east, north]
    except Exception as e:
        logger.warning(f"bounds_wgs84 转换失败: {e}")

    db_data = {
        "file_name": new_name if new_name.endswith(".tif") else f"{new_name}.tif",
        "file_path": tmp_path,
        "cog_path": f"/data/{cog_filename}",
        "bundle_id": final_bundle_id,
        "index_id": get_next_index_id(),
        "crs": metadata.get("crs"),
        "bounds": metadata.get("bounds"),
        "bounds_wgs84": bounds_wgs84,
        "center": metadata.get("center"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "bands": bands_count,
        "data_type": metadata.get("data_type"),
        "resolution_x": metadata.get("resolution")[0] if metadata.get("resolution") else None,
        "resolution_y": metadata.get("resolution")[1] if metadata.get("resolution") else None
    }

    new_record = await RasterCRUD.create_raster(db, db_data)
    await db.commit()
    await RasterFieldCRUD(db).ingest_from_metadata(new_record.index_id, db_data)
    return {"status": "success", "id": new_record.id, "cog_url": db_data["cog_path"]}


async def _get_band_paths(db: AsyncSession, band_ids: List[int]) -> List[str]:
    """
    批量获取 band path
    """
    unique_ids = list(dict.fromkeys(band_ids))
    stmt = select(models.RasterMetadata).where(
        models.RasterMetadata.index_id.in_(unique_ids)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    if len(records) != len(unique_ids):
        raise HTTPException(status_code=404, detail="部分波段ID不存在")
    record_map = {r.index_id: r for r in records}
    paths = []
    for band_id in band_ids:
        path = resolve_raster_record_path(record_map[band_id])
        if not path:
            raise HTTPException(
                status_code=404,
                detail=f"Raster file not found for index_id={band_id}",
            )
        paths.append(path)
    return paths


def _submit_cluster_job_or_none(
    *,
    operation: str,
    inputs: dict,
    new_name: str,
    prefix: str,
    params: dict | None = None,
    raster_index_id: int | str | None = None,
) -> dict | None:
    if not worker_bridge.cluster_enabled():
        return None
    try:
        return worker_bridge.submit_raster_product_job(
            operation=operation,
            inputs=inputs,
            new_name=new_name,
            prefix=prefix,
            params=params,
            raster_index_id=raster_index_id,
        )
    except worker_bridge.ClusterDispatchError as exc:
        if worker_bridge.cluster_fallback_enabled():
            logger.warning(
                "Falling back to inline processing for %s after cluster dispatch failed: %s",
                operation,
                exc,
            )
            return None
        raise HTTPException(
            status_code=503,
            detail=f"Compute cluster dispatch failed: {exc}",
        ) from exc


async def process_index_task(db: AsyncSession, band_ids: list, new_name: str, prefix: str, processor_func):
    try:

        paths = await _get_band_paths(db, band_ids)
        cluster_result = _submit_cluster_job_or_none(
            operation=prefix,
            inputs={"paths": paths},
            new_name=new_name,
            prefix=prefix,
            raster_index_id=band_ids[0] if band_ids else None,
        )
        if cluster_result is not None:
            return cluster_result

        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)
        processor_func(*paths, tmp_path)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)
        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)

    except Exception as e:
        logger.error(f"{prefix} 计算失败: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_extraction_task(db: AsyncSession, band_ids: List[int], new_name: str, prefix: str, processor_func, **kwargs):
    try:
        paths = await _get_band_paths(db, band_ids)
        operation = {
            "veg": "vegetation",
            "water": "water",
            "building": "building",
            "cloud": "cloud",
        }.get(prefix, prefix)
        cluster_result = _submit_cluster_job_or_none(
            operation=operation,
            inputs={"paths": paths},
            new_name=new_name,
            prefix=prefix,
            params=kwargs,
            raster_index_id=band_ids[0] if band_ids else None,
        )
        if cluster_result is not None:
            return cluster_result

        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)
        processor_func(paths, tmp_path, **kwargs)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)
        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)

    except Exception as e:
        logger.error(f"{prefix} 提取任务失败: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_calculator_task(
    db: AsyncSession,
    var_mapping: dict[str, int],
    expression: str,
    new_name: str,
    prefix: str
):
    try:
        raster_ids = list(var_mapping.values())
        paths = await _get_band_paths(db, raster_ids)

        path_mapping = {
            var_name: paths[index]
            for index, (var_name, _) in enumerate(var_mapping.items())
        }

        cluster_result = _submit_cluster_job_or_none(
            operation="calculator",
            inputs={"path_mapping": path_mapping},
            new_name=new_name,
            prefix=prefix,
            params={"expression": expression},
            raster_index_id=raster_ids[0] if raster_ids else None,
        )
        if cluster_result is not None:
            return cluster_result

        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        RasterProcessor.run_raster_calculator(path_mapping, expression, tmp_path)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        with rasterio.open(tmp_path) as src:
            actual_bands = src.count

        return await save_to_db(
            db, task_id, new_name, tmp_path,
            cog_filename, cog_path, prefix,
            bands_count=actual_bands
        )

    except Exception as e:
        logger.error(f"栅格计算器任务失败: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def get_dynamic_band_ids(request: Request) -> List[int]:
    form_data = await request.form()
    id_keys = [
        k for k in form_data.keys()
        if re.match(r'^id_\d+$', k)]
    id_keys.sort(key=lambda x: int(x.split('_')[1]))
    return [int(form_data[k]) for k in id_keys]


async def process_raster_to_vector_task(
    db: AsyncSession,
    raster_index_id: int,
    project_id: UUID,
    new_name: str,
    band_index: int = 1,
    skip_nodata: bool = True,
    skip_zero: bool = True,
    max_features: int = 10000,
    simplify_tolerance: float = 0.0,
):
    from services.data_service.bridges.vector_bridge import (
        internal_bulk_create_features,
        internal_create_fields,
        internal_create_layer,
    )

    try:
        stmt = select(models.RasterMetadata).where(
            models.RasterMetadata.index_id == raster_index_id
        )
        res = await db.execute(stmt)
        raster_record = res.scalar_one_or_none()
        if not raster_record:
            raise HTTPException(status_code=404, detail="Raster not found")

        raster_path = resolve_raster_record_path(raster_record)
        if not raster_path:
            raise HTTPException(status_code=404, detail="Raster file not found")

        features = RasterProcessor.run_vectorization(
            raster_path=raster_path,
            band_index=band_index,
            skip_nodata=skip_nodata,
            skip_zero=skip_zero,
            max_features=max_features,
            simplify_tolerance=simplify_tolerance,
        )
        if not features:
            raise HTTPException(
                status_code=400,
                detail="No vector features were generated from the selected raster band",
            )

        layer = await internal_create_layer(
            project_id=project_id,
            name=new_name,
            source_raster_index_id=raster_record.index_id,
        )
        layer_id = layer["id"]

        await internal_create_fields(
            layer_id,
            [
                {
                    "field_name": "raster_value",
                    "field_alias": "Raster Value",
                    "field_type": "number",
                    "field_order": 0,
                },
                {
                    "field_name": "band_index",
                    "field_alias": "Band Index",
                    "field_type": "number",
                    "field_order": 1,
                },
                {
                    "field_name": "category",
                    "field_alias": "Category",
                    "field_type": "string",
                    "field_order": 2,
                },
            ],
        )
        imported_count = await internal_bulk_create_features(layer_id, features)

        return {
            "status": "success",
            "layer_id": layer_id,
            "layer": layer,
            "feature_count": imported_count,
            "source_raster_index_id": raster_record.index_id,
        }

    except Exception as e:
        logger.error(f"raster-to-vector conversion failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_rasterize_task(
        db: AsyncSession,
        layer_id: UUID,
        ref_index_id: int,
        new_name: str,
        prefix: str,
        processor_func,
        fetch_func: Callable
):
    """
    矢量转栅格通用任务
    :param fetch_func: 跨服务获取矢量的函数 (internal_fetch_features)
    :param processor_func: RasterProcessor.run_rasterization
    """
    try:
        # 1. 获取参考影像路径
        stmt = select(models.RasterMetadata).where(models.RasterMetadata.index_id == ref_index_id)
        res = await db.execute(stmt)
        ref_record = res.scalar_one_or_none()
        if not ref_record:
            raise HTTPException(status_code=404, detail="参考影像不存在")

        # 2. 跨服务获取矢量数据 (GeoJSON Features)
        features = await fetch_func(layer_id)
        if not features:
            raise HTTPException(status_code=400, detail="该图层无有效矢量要素")

        # 3. 准备路径
        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        # 4. 执行转换 (注意：processor_func 需要处理坐标对齐)
        processor_func(features, ref_record.file_path, tmp_path)

        # 5. 转换为 COG
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        # 6. 入库
        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)

    except Exception as e:
        logger.error(f"{prefix} 转换失败: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
