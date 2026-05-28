"""Cluster-side raster product workflow.

This module is the boundary between the compute cluster and the reusable
algorithm layer. FastAPI routes submit a job description; the worker runs the
algorithm, creates the COG, persists raster metadata, and reports the final
product through the normal task status channel.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

import rasterio

from functions.common.snowflake_utils import get_next_index_id
from services.data_service.models import RasterField, RasterMetadata
from services.data_service.processor import RasterProcessor
from worker_cluster.app import celery_app
from worker_cluster.bridge.db_sync import get_sync_db
from worker_cluster.tasks.base import BaseRasterTask


logger = logging.getLogger("worker.algorithm.raster_product")


_FIELD_TYPE_MAP = {
    str: "string",
    int: "number",
    float: "number",
    bool: "boolean",
}


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _file_name(name: str) -> str:
    safe = os.path.basename(name.strip() or "raster_result.tif")
    return safe if safe.lower().endswith(".tif") else f"{safe}.tif"


def _public_cog_path(cog_path: str) -> str:
    return f"/data/{os.path.basename(cog_path)}"


def _path_list(inputs: dict[str, Any], *, min_count: int = 1) -> list[str]:
    paths = list(inputs.get("paths") or [])
    if len(paths) < min_count:
        raise ValueError(f"Expected at least {min_count} input path(s)")
    return paths


def _run_operation(
    operation: str,
    inputs: dict[str, Any],
    params: dict[str, Any],
    raw_path: str,
) -> dict[str, Any]:
    index_runners: dict[str, Callable[[str, str, str], None]] = {
        "ndvi": RasterProcessor.calculate_ndvi,
        "ndwi": RasterProcessor.calculate_ndwi,
        "ndbi": RasterProcessor.calculate_ndbi,
        "mndwi": RasterProcessor.calculate_mndwi,
    }
    extraction_runners: dict[str, Callable[..., None]] = {
        "vegetation": RasterProcessor.run_vegetation_extraction,
        "water": RasterProcessor.run_water_extraction,
        "building": RasterProcessor.run_building_extraction,
        "cloud": RasterProcessor.run_cloud_extraction,
    }

    if operation in index_runners:
        band1_path, band2_path = _path_list(inputs, min_count=2)[:2]
        index_runners[operation](band1_path, band2_path, raw_path)
        return {"operation": operation}

    if operation in extraction_runners:
        paths = _path_list(inputs, min_count=1)
        extraction_runners[operation](paths, raw_path, **params)
        return {"operation": operation}

    if operation == "calculator":
        path_mapping = inputs.get("path_mapping") or {}
        expression = params.get("expression")
        if not path_mapping:
            raise ValueError("Calculator job requires a path mapping")
        if not expression:
            raise ValueError("Calculator job requires an expression")
        RasterProcessor.run_raster_calculator(path_mapping, expression, raw_path)
        return {"operation": operation, "expression": expression}

    if operation == "merge_bands":
        RasterProcessor.merge_bands(_path_list(inputs, min_count=1), raw_path)
        return {"operation": operation}

    if operation == "extract_bands":
        source_path = _path_list(inputs, min_count=1)[0]
        band_indices = params.get("band_indices") or []
        if not band_indices:
            raise ValueError("Band extraction job requires band_indices")
        RasterProcessor.extract_bands(source_path, raw_path, [int(i) for i in band_indices])
        return {"operation": operation, "band_indices": band_indices}

    if operation == "clip_raster_by_vector":
        raster_path = inputs.get("raster_path")
        geometries = inputs.get("geometries") or []
        if not raster_path:
            raise ValueError("Clip job requires raster_path")
        if not geometries:
            raise ValueError("Clip job requires geometries")
        clip_meta = RasterProcessor.clip_raster_by_vector(
            raster_path=raster_path,
            output_path=raw_path,
            geojson_geometries=geometries,
            src_vector_crs=params.get("src_vector_crs", "EPSG:4326"),
            crop=bool(params.get("crop", True)),
            nodata=params.get("nodata"),
            all_touched=bool(params.get("all_touched", False)),
        )
        return {"operation": operation, "clip_meta": clip_meta}

    raise ValueError(f"Unsupported raster operation: {operation}")


def _metadata_payload(
    *,
    raw_path: str,
    cog_path: str,
    cog_public_path: str,
    new_name: str,
    prefix: str,
    output_id: str,
    bundle_id: str | None,
    bands_count: int,
) -> dict[str, Any]:
    metadata = RasterProcessor.extract_metadata(raw_path)
    resolution = metadata.get("resolution")
    return {
        "file_name": _file_name(new_name),
        "file_path": raw_path,
        "cog_path": cog_public_path,
        "bundle_id": bundle_id or f"{prefix}_{output_id[:8]}",
        "index_id": get_next_index_id(),
        "crs": metadata.get("crs"),
        "bounds": metadata.get("bounds"),
        "bounds_wgs84": metadata.get("bounds_wgs84"),
        "center": metadata.get("center"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "bands": bands_count,
        "data_type": metadata.get("data_type"),
        "resolution_x": resolution[0] if resolution else None,
        "resolution_y": resolution[1] if resolution else None,
        "physical_cog_path": cog_path,
    }


def _ingest_system_fields(db, raster_index_id: int, metadata: dict[str, Any]) -> None:
    existing_rows = (
        db.query(RasterField.field_name)
        .filter(RasterField.raster_index_id == raster_index_id)
        .all()
    )
    existing_names = {row[0] for row in existing_rows}
    for order, (key, value) in enumerate(metadata.items()):
        if key == "physical_cog_path" or key in existing_names:
            continue
        field_type = _FIELD_TYPE_MAP.get(type(value) if value is not None else str, "string")
        db.add(
            RasterField(
                raster_index_id=raster_index_id,
                field_name=key,
                field_alias=key,
                field_type=field_type,
                field_order=order,
                is_system=True,
            )
        )


def _register_raster_product(metadata: dict[str, Any]) -> dict[str, Any]:
    with get_sync_db() as db:
        record = RasterMetadata(
            file_name=metadata["file_name"],
            bundle_id=metadata.get("bundle_id"),
            index_id=metadata["index_id"],
            file_path=metadata["file_path"],
            cog_path=metadata["cog_path"],
            crs=metadata.get("crs"),
            bounds=metadata.get("bounds"),
            bounds_wgs84=metadata.get("bounds_wgs84"),
            center=metadata.get("center"),
            width=metadata.get("width"),
            height=metadata.get("height"),
            bands=metadata.get("bands"),
            data_type=metadata.get("data_type"),
            resolution_x=metadata.get("resolution_x"),
            resolution_y=metadata.get("resolution_y"),
        )
        db.add(record)
        db.flush()
        _ingest_system_fields(db, record.index_id, metadata)
        return {
            "status": "success",
            "id": record.id,
            "index_id": record.index_id,
            "cog_url": record.cog_path,
            "file_path": record.file_path,
            "cog_path": record.cog_path,
            "physical_cog_path": metadata["physical_cog_path"],
        }


@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.algorithm.raster_product",
    queue="index",
)
def raster_product_task(
    self,
    operation: str,
    inputs: dict[str, Any],
    output: dict[str, str],
    registration: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a raster algorithm and register the generated product."""

    params = params or {}
    raw_path = output["raw_path"]
    cog_path = output["cog_path"]
    cog_public_path = output.get("cog_public_path") or _public_cog_path(cog_path)
    output_id = registration.get("output_id") or os.path.basename(raw_path).split("_", 1)[0]
    prefix = registration.get("prefix") or operation

    try:
        self.report(10, f"Preparing {operation} job")
        _ensure_parent_dir(raw_path)
        _ensure_parent_dir(cog_path)

        self.report(25, f"Running {operation} algorithm")
        operation_result = _run_operation(operation, inputs, params, raw_path)

        self.report(70, "Converting result to COG")
        RasterProcessor.convert_to_cog(raw_path, cog_path)

        with rasterio.open(raw_path) as src:
            bands_count = src.count

        self.report(85, "Registering raster product")
        metadata = _metadata_payload(
            raw_path=raw_path,
            cog_path=cog_path,
            cog_public_path=cog_public_path,
            new_name=registration["new_name"],
            prefix=prefix,
            output_id=output_id,
            bundle_id=registration.get("bundle_id"),
            bands_count=bands_count,
        )
        product = _register_raster_product(metadata)
        product.update(
            {
                "operation": operation,
                "queue": "index",
                "result": operation_result,
            }
        )
        logger.info("[raster_product] done operation=%s index_id=%s", operation, product["index_id"])
        return product
    except Exception as exc:
        logger.exception("[raster_product] failed operation=%s", operation)
        raise self.retry(exc=exc, countdown=10)
