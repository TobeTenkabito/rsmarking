import os
import uuid
import logging
import re
import rasterio
from uuid import UUID
from fastapi import HTTPException, Request
from typing import Any, List, Callable
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
        logger.error(f"COG conversion failed: {str(e)}")


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
        logger.warning(f"bounds_wgs84 conversion failed: {e}")

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
    batch fetch band path
    """
    unique_ids = list(dict.fromkeys(band_ids))
    stmt = select(models.RasterMetadata).where(
        models.RasterMetadata.index_id.in_(unique_ids)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    if len(records) != len(unique_ids):
        raise HTTPException(status_code=404, detail="Some band IDs do not exist")
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
        logger.error(f"{prefix} calculation failed: {str(e)}")
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
        logger.error(f"{prefix} extraction task failed: {str(e)}")
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
        logger.error(f"Raster calculator task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_resampling_task(
    db: AsyncSession,
    raster_id: int,
    target_resolution_x: float,
    target_resolution_y: float | None,
    resolution_unit: str,
    resampling_method: str,
    new_name: str,
):
    try:
        stmt = select(models.RasterMetadata).where(
            models.RasterMetadata.index_id == raster_id
        )
        res = await db.execute(stmt)
        raster_record = res.scalar_one_or_none()
        if not raster_record:
            raise HTTPException(status_code=404, detail="Raster not found")

        input_path = resolve_raster_record_path(raster_record)
        if not input_path:
            raise HTTPException(status_code=404, detail="Raster file not found")

        params = {
            "target_resolution_x": target_resolution_x,
            "target_resolution_y": target_resolution_y,
            "resolution_unit": resolution_unit,
            "resampling_method": resampling_method,
        }
        cluster_result = _submit_cluster_job_or_none(
            operation="resample",
            inputs={"paths": [input_path]},
            new_name=new_name,
            prefix="resampled",
            params=params,
            raster_index_id=raster_id,
        )
        if cluster_result is not None:
            return cluster_result

        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_resampled_raw.tif")
        cog_filename = f"{task_id}_resampled.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        RasterProcessor.resample_raster(
            input_path=input_path,
            output_path=tmp_path,
            target_resolution_x=target_resolution_x,
            target_resolution_y=target_resolution_y,
            resolution_unit=resolution_unit,
            resampling_method=resampling_method,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        with rasterio.open(tmp_path) as src:
            actual_bands = src.count

        return await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            "resampled",
            bands_count=actual_bands,
            metadata_source=tmp_path,
        )

    except Exception as e:
        logger.error(f"resampling task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_atmospheric_correction_task(
    db: AsyncSession,
    raster_id: int,
    method: str,
    sensor: str,
    new_name: str,
    scale_factor: float | None = None,
    offset: float | None = None,
    dark_percentile: float = 1.0,
    bright_percentile: float = 99.0,
    clamp: bool = True,
):
    try:
        stmt = select(models.RasterMetadata).where(
            models.RasterMetadata.index_id == raster_id
        )
        res = await db.execute(stmt)
        raster_record = res.scalar_one_or_none()
        if not raster_record:
            raise HTTPException(status_code=404, detail="Raster not found")

        input_path = resolve_raster_record_path(raster_record)
        if not input_path:
            raise HTTPException(status_code=404, detail="Raster file not found")

        params = {
            "method": method,
            "sensor": sensor,
            "scale_factor": scale_factor,
            "offset": offset,
            "dark_percentile": dark_percentile,
            "bright_percentile": bright_percentile,
            "clamp": clamp,
        }
        cluster_result = _submit_cluster_job_or_none(
            operation="atmospheric_correction",
            inputs={"paths": [input_path]},
            new_name=new_name,
            prefix="atmospheric",
            params=params,
            raster_index_id=raster_id,
        )
        if cluster_result is not None:
            return cluster_result

        task_id = str(uuid.uuid4())
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(COG_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_atmospheric_raw.tif")
        cog_filename = f"{task_id}_atmospheric.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        correction_meta = RasterProcessor.atmospheric_correction(
            input_path=input_path,
            output_path=tmp_path,
            method=method,
            sensor=sensor,
            scale_factor=scale_factor,
            offset=offset,
            dark_percentile=dark_percentile,
            bright_percentile=bright_percentile,
            clamp=clamp,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        with rasterio.open(tmp_path) as src:
            actual_bands = src.count

        result = await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            "atmospheric",
            bands_count=actual_bands,
            metadata_source=tmp_path,
        )
        result["correction"] = correction_meta
        return result

    except Exception as e:
        logger.error(f"atmospheric correction task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_radiometric_calibration_task(
    db: AsyncSession,
    raster_id: int,
    new_name: str,
    calibration_type: str = "auto",
    scale_factor: float | None = None,
    offset: float | None = None,
    radiance_mult: float | None = None,
    radiance_add: float | None = None,
    reflectance_mult: float | None = None,
    reflectance_add: float | None = None,
    sun_elevation: float | None = None,
    earth_sun_distance: float = 1.0,
    solar_irradiance: float | None = None,
    sun_elevation_correction: bool = True,
    clamp: bool = False,
):
    try:
        raster_record = await _get_raster_record_or_404(db, raster_id)
        input_path = _resolve_record_path_or_404(raster_record)

        task_id = str(uuid.uuid4())
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(COG_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_radiometric_raw.tif")
        cog_filename = f"{task_id}_radiometric.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        calibration_meta = RasterProcessor.radiometric_calibration(
            input_path=input_path,
            output_path=tmp_path,
            calibration_type=calibration_type,
            scale_factor=scale_factor,
            offset=offset,
            radiance_mult=radiance_mult,
            radiance_add=radiance_add,
            reflectance_mult=reflectance_mult,
            reflectance_add=reflectance_add,
            sun_elevation=sun_elevation,
            earth_sun_distance=earth_sun_distance,
            solar_irradiance=solar_irradiance,
            sun_elevation_correction=sun_elevation_correction,
            clamp=clamp,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        with rasterio.open(tmp_path) as src:
            actual_bands = src.count

        result = await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            "radiometric",
            bands_count=actual_bands,
            metadata_source=tmp_path,
        )
        result["calibration"] = calibration_meta
        return result
    except Exception as e:
        logger.error(f"radiometric calibration task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_geometric_correction_task(
    db: AsyncSession,
    raster_id: int,
    new_name: str,
    dst_crs: str | None = None,
    resampling_method: str = "bilinear",
    target_resolution_x: float | None = None,
    target_resolution_y: float | None = None,
    shift_x: float = 0.0,
    shift_y: float = 0.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    rotation_degrees: float = 0.0,
    gcps: list[dict[str, float]] | None = None,
):
    try:
        raster_record = await _get_raster_record_or_404(db, raster_id)
        input_path = _resolve_record_path_or_404(raster_record)

        task_id = str(uuid.uuid4())
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(COG_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_geometric_raw.tif")
        cog_filename = f"{task_id}_geometric.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        correction_meta = RasterProcessor.geometric_correction(
            input_path=input_path,
            output_path=tmp_path,
            dst_crs=dst_crs,
            resampling_method=resampling_method,
            target_resolution_x=target_resolution_x,
            target_resolution_y=target_resolution_y,
            shift_x=shift_x,
            shift_y=shift_y,
            scale_x=scale_x,
            scale_y=scale_y,
            rotation_degrees=rotation_degrees,
            gcps=gcps,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        with rasterio.open(tmp_path) as src:
            actual_bands = src.count

        result = await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            "geometric",
            bands_count=actual_bands,
            metadata_source=tmp_path,
        )
        result["correction"] = correction_meta
        return result
    except Exception as e:
        logger.error(f"geometric correction task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_dem_analysis_task(
    db: AsyncSession,
    raster_id: int,
    operation: str,
    new_name: str,
    band_index: int = 1,
    z_factor: float = 1.0,
    slope_unit: str = "degrees",
    hillshade_azimuth: float = 315.0,
    hillshade_altitude: float = 45.0,
    relief_window_size: int = 3,
    min_slope_degrees: float = 0.1,
):
    try:
        raster_record = await _get_raster_record_or_404(db, raster_id)
        input_path = _resolve_record_path_or_404(raster_record)
        prefix = f"dem_{_safe_operation_name(operation)}"

        task_id = str(uuid.uuid4())
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(COG_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        dem_meta = RasterProcessor.dem_analysis(
            input_path=input_path,
            output_path=tmp_path,
            operation=operation,
            band_index=band_index,
            z_factor=z_factor,
            slope_unit=slope_unit,
            hillshade_azimuth=hillshade_azimuth,
            hillshade_altitude=hillshade_altitude,
            relief_window_size=relief_window_size,
            min_slope_degrees=min_slope_degrees,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        result = await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            prefix,
            bands_count=1,
            metadata_source=tmp_path,
        )
        result["dem_analysis"] = dem_meta
        return result
    except Exception as e:
        logger.error(f"DEM analysis task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_raster_transform_task(
    db: AsyncSession,
    raster_id: int,
    transform_type: str,
    new_name: str,
    band_index: int = 1,
    fourier_output: str = "magnitude",
    wavelet_output: str = "detail_energy",
    wavelet_level: int = 1,
    pca_components: int = 3,
    pca_standardize: bool = False,
):
    try:
        raster_record = await _get_raster_record_or_404(db, raster_id)
        input_path = _resolve_record_path_or_404(raster_record)
        prefix = f"raster_{_safe_operation_name(transform_type)}"

        task_id = str(uuid.uuid4())
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(COG_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        transform_meta = RasterProcessor.raster_transform_analysis(
            input_path=input_path,
            output_path=tmp_path,
            transform_type=transform_type,
            band_index=band_index,
            fourier_output=fourier_output,
            wavelet_output=wavelet_output,
            wavelet_level=wavelet_level,
            pca_components=pca_components,
            pca_standardize=pca_standardize,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        with rasterio.open(tmp_path) as src:
            actual_bands = src.count

        result = await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            prefix,
            bands_count=actual_bands,
            metadata_source=tmp_path,
        )
        result["raster_transform"] = transform_meta
        return result
    except Exception as e:
        logger.error(f"raster transform task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_supervised_classification_task(
    db: AsyncSession,
    raster_id: int,
    samples: list[dict[str, Any]],
    classifier: str,
    new_name: str,
    band_indices: list[int] | None = None,
    n_estimators: int = 100,
    random_seed: int = 13,
    smoothing: int = 0,
):
    try:
        raster_record = await _get_raster_record_or_404(db, raster_id)
        input_path = _resolve_record_path_or_404(raster_record)

        task_id = str(uuid.uuid4())
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(COG_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_supervised_classification_raw.tif")
        cog_filename = f"{task_id}_supervised_classification.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        classification_meta = RasterProcessor.supervised_classification(
            input_path=input_path,
            output_path=tmp_path,
            samples=samples,
            classifier=classifier,
            band_indices=band_indices,
            n_estimators=n_estimators,
            random_seed=random_seed,
            smoothing=smoothing,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        result = await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            "supervised_classification",
            bands_count=1,
            metadata_source=tmp_path,
        )
        result["classification"] = classification_meta
        return result
    except Exception as e:
        logger.error(f"supervised classification task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_unsupervised_classification_task(
    db: AsyncSession,
    raster_id: int,
    n_classes: int,
    method: str,
    new_name: str,
    band_indices: list[int] | None = None,
    max_samples: int = 50000,
    random_seed: int = 13,
    smoothing: int = 0,
):
    try:
        raster_record = await _get_raster_record_or_404(db, raster_id)
        input_path = _resolve_record_path_or_404(raster_record)

        task_id = str(uuid.uuid4())
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(COG_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_unsupervised_classification_raw.tif")
        cog_filename = f"{task_id}_unsupervised_classification.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        classification_meta = RasterProcessor.unsupervised_classification(
            input_path=input_path,
            output_path=tmp_path,
            n_classes=n_classes,
            method=method,
            band_indices=band_indices,
            max_samples=max_samples,
            random_seed=random_seed,
            smoothing=smoothing,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        result = await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            "unsupervised_classification",
            bands_count=1,
            metadata_source=tmp_path,
        )
        result["classification"] = classification_meta
        return result
    except Exception as e:
        logger.error(f"unsupervised classification task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def process_deep_learning_segmentation_task(
    db: AsyncSession,
    raster_id: int,
    new_name: str,
    model_path: str | None = None,
    backend: str = "auto",
    n_classes: int = 2,
    band_indices: list[int] | None = None,
    threshold: float = 0.5,
    random_seed: int = 13,
    max_samples: int = 50000,
    compactness: float = 0.15,
    smoothing: int = 1,
):
    try:
        raster_record = await _get_raster_record_or_404(db, raster_id)
        input_path = _resolve_record_path_or_404(raster_record)

        task_id = str(uuid.uuid4())
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(COG_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_deep_segmentation_raw.tif")
        cog_filename = f"{task_id}_deep_segmentation.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        segmentation_meta = RasterProcessor.deep_learning_segmentation(
            input_path=input_path,
            output_path=tmp_path,
            model_path=model_path,
            backend=backend,
            n_classes=n_classes,
            band_indices=band_indices,
            threshold=threshold,
            random_seed=random_seed,
            max_samples=max_samples,
            compactness=compactness,
            smoothing=smoothing,
        )
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        result = await save_to_db(
            db,
            task_id,
            new_name,
            tmp_path,
            cog_filename,
            cog_path,
            "deep_segmentation",
            bands_count=1,
            metadata_source=tmp_path,
        )
        result["segmentation"] = segmentation_meta
        return result
    except Exception as e:
        logger.error(f"deep learning segmentation task failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


async def _get_raster_record_or_404(db: AsyncSession, raster_id: int) -> models.RasterMetadata:
    stmt = select(models.RasterMetadata).where(models.RasterMetadata.index_id == raster_id)
    res = await db.execute(stmt)
    raster_record = res.scalar_one_or_none()
    if not raster_record:
        raise HTTPException(status_code=404, detail="Raster not found")
    return raster_record


def _resolve_record_path_or_404(raster_record: models.RasterMetadata) -> str:
    input_path = resolve_raster_record_path(raster_record)
    if not input_path:
        raise HTTPException(status_code=404, detail="Raster file not found")
    return input_path


def _safe_operation_name(operation: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", str(operation or "analysis").strip().lower())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "analysis"


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
    generic vector-to-raster task
    :param fetch_func: function for cross-service vector fetching (internal_fetch_features)
    :param processor_func: RasterProcessor.run_rasterization
    """
    try:
        # 1. get reference imagery path
        stmt = select(models.RasterMetadata).where(models.RasterMetadata.index_id == ref_index_id)
        res = await db.execute(stmt)
        ref_record = res.scalar_one_or_none()
        if not ref_record:
            raise HTTPException(status_code=404, detail="Reference imagery does not exist")

        # 2. fetch vector data across services (GeoJSON Features)
        features = await fetch_func(layer_id)
        if not features:
            raise HTTPException(status_code=400, detail="This layer has no valid vector features")

        # 3. prepare paths
        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_{prefix}_raw.tif")
        cog_filename = f"{task_id}_{prefix}.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)

        # 4. execute conversion (note:processor_func must handle coordinate alignment)
        processor_func(features, ref_record.file_path, tmp_path)

        # 5. convert to COG
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        # 6. write to database
        return await save_to_db(db, task_id, new_name, tmp_path, cog_filename, cog_path, prefix)

    except Exception as e:
        logger.error(f"{prefix} conversion failed: {str(e)}")
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
