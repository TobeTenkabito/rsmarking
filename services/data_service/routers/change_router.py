"""
change_router.py - Change detection routes

POST /change/detect
"""

import os
import time
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from services.data_service.database import get_db
from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.processor import RasterProcessor
from functions.common.snowflake_utils import get_next_index_id as generate_index_id
from functions.implement.change_ops import (
    band_diff,
    band_ratio,
    index_diff,
)
from functions.implement.io_ops import (
    build_raster_overviews,
    convert_raster_to_cog,
)

logger = logging.getLogger("data_service.change_router")
router = APIRouter(prefix="/change", tags=["Change Detection"])



def _resolve_storage_dir(env_key: str, relative: str) -> str:
    """
    Read the environment variable first.
    If missing, walk upward from this file to find the project root containing storage, then append the relative path.
    Ensure the directory exists.
    """
    from_env = os.environ.get(env_key, "").strip()
    if from_env:
        p = Path(from_env)
    else:
        # Walk upward from this file until a root containing the storage subdirectory is found.
        current = Path(__file__).resolve()
        root = current
        for parent in current.parents:
            if (parent / "storage").exists():
                root = parent
                break
        p = root / "storage" / relative

    p.mkdir(parents=True, exist_ok=True)
    return str(p)

COG_DIR = _resolve_storage_dir("COG_DIR", "cog")
RAW_DIR = _resolve_storage_dir("RAW_DIR", "raw")


class BandDiffRequest(BaseModel):
    index_id_t1: int = Field(..., description="Earlier imagery index_id")
    index_id_t2: int = Field(..., description="Later imagery index_id")
    band_idx: int = Field(1, description="Band to use (1-based)")
    threshold: float = Field(0.1, description="Change detection threshold")
    threshold_mode: str = Field("abs", description="abs / positive / negative")
    output_mask: bool = Field(True, description="Whether to also output a binary mask")


class BandRatioRequest(BaseModel):
    index_id_t1: int
    index_id_t2: int
    band_idx: int = 1
    threshold: float = 0.2
    output_mask: bool = True


class IndexDiffRequest(BaseModel):
    # T1 two band index_ids
    index_id_t1_b1: int = Field(..., description="T1 band 1 index_id (for example Red)")
    index_id_t1_b2: int = Field(..., description="T1 band 2 index_id (for example NIR)")
    # T2 two band index_ids
    index_id_t2_b1: int = Field(..., description="T2 band 1 index_id")
    index_id_t2_b2: int = Field(..., description="T2 band 2 index_id")
    index_type: str = Field("ndvi", description="ndvi / ndwi / ndbi / mndwi")
    threshold: float = 0.15
    threshold_mode: str = "abs"
    output_mask: bool = True


class ChangeDetectResponse(BaseModel):
    diff_index_id: int
    mask_index_id: int | None
    method: str
    change_pixel_count: int | None
    change_area_ratio: float | None


async def _get_raster_path(db: AsyncSession, index_id: int, label: str) -> str:
    record = await RasterCRUD.get_raster_by_index_id(db, index_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"{label} (index_id={index_id}) does not exist in the database"
        )

    # First priority: use the full path stored in the database
    for full_path in [record.cog_path, record.file_path]:
        if full_path and os.path.exists(full_path):
            logger.debug(f"[_get_raster_path] {label} -> {full_path}")
            return full_path

    # Fallback: extract the file name and scan configured directories
    ref_path = record.cog_path or record.file_path
    if not ref_path:
        raise HTTPException(
            status_code=404,
            detail=f"{label} (index_id={index_id}) has no path fields in the database"
        )

    disk_filename = os.path.basename(ref_path)
    for d in [COG_DIR, RAW_DIR]:
        candidate = os.path.join(d, disk_filename)
        if os.path.exists(candidate):
            logger.debug(f"[_get_raster_path] {label} fallback -> {candidate}")
            return candidate

    raise HTTPException(
        status_code=404,
        detail=(
            f"{label} file not found\n"
            f"  cog_path : {record.cog_path}\n"
            f"  file_path: {record.file_path}\n"
            f"  Scanned directories : {[COG_DIR, RAW_DIR]}"
        )
    )


async def _register_result(
    db: AsyncSession,
    raw_path: str,
    file_name: str,
    bundle_id: str,
) -> int:
    new_index_id = generate_index_id()
    cog_path = os.path.join(COG_DIR, f"{new_index_id}.tif")

    convert_raster_to_cog(raw_path, cog_path)
    build_raster_overviews(cog_path)

    meta = RasterProcessor.extract_metadata(cog_path)
    meta.update({
        "file_name": file_name,
        "index_id":  new_index_id,
        "file_path": raw_path,
        "cog_path":  cog_path,
        "bundle_id": bundle_id,
    })
    await RasterCRUD.create_raster(db, meta)
    await db.commit()
    return new_index_id


def _calc_change_ratio(change_pixel_count: int | None, path: str) -> float | None:
    """Calculate the ratio of changed pixels to total pixels."""
    if change_pixel_count is None:
        return None
    try:
        import rasterio
        with rasterio.open(path) as src:
            total = src.width * src.height
        return round(change_pixel_count / total, 6) if total > 0 else None
    except Exception:
        return None


@router.post("/band-diff", response_model=ChangeDetectResponse, summary="Single-band difference change detection")
async def detect_band_diff(
    req: BandDiffRequest,
    db: AsyncSession = Depends(get_db),
):
    path_t1 = await _get_raster_path(db, req.index_id_t1, "t1")
    path_t2 = await _get_raster_path(db, req.index_id_t2, "t2")

    bundle_id = f"change_banddiff_{req.index_id_t1}_{req.index_id_t2}_{int(time.time())}"
    diff_raw = os.path.join(RAW_DIR, f"{bundle_id}_diff.tif")
    mask_raw = os.path.join(RAW_DIR, f"{bundle_id}_mask.tif") if req.output_mask else None

    result = band_diff(
        path_t1=path_t1,
        path_t2=path_t2,
        output_diff_path=diff_raw,
        output_mask_path=mask_raw,
        band_idx=req.band_idx,
        threshold=req.threshold,
        threshold_mode=req.threshold_mode,
    )

    diff_index_id = await _register_result(db, diff_raw, f"band_diff_{bundle_id}", bundle_id)
    mask_index_id = None
    if mask_raw:
        mask_index_id = await _register_result(db, mask_raw, f"band_diff_mask_{bundle_id}", bundle_id)

    return ChangeDetectResponse(
        diff_index_id=diff_index_id,
        mask_index_id=mask_index_id,
        method="band_diff",
        change_pixel_count=result["change_pixel_count"],
        change_area_ratio=_calc_change_ratio(result["change_pixel_count"], diff_raw),
    )


@router.post("/band-ratio", response_model=ChangeDetectResponse, summary="Single-band ratio change detection")
async def detect_band_ratio(
    req: BandRatioRequest,
    db: AsyncSession = Depends(get_db),
):
    path_t1 = await _get_raster_path(db, req.index_id_t1, "t1")
    path_t2 = await _get_raster_path(db, req.index_id_t2, "t2")

    bundle_id = f"change_ratio_{req.index_id_t1}_{req.index_id_t2}_{int(time.time())}"
    diff_raw = os.path.join(RAW_DIR, f"{bundle_id}_ratio.tif")
    mask_raw = os.path.join(RAW_DIR, f"{bundle_id}_mask.tif") if req.output_mask else None

    result = band_ratio(
        path_t1=path_t1,
        path_t2=path_t2,
        output_diff_path=diff_raw,
        output_mask_path=mask_raw,
        band_idx=req.band_idx,
        threshold=req.threshold,
    )

    diff_index_id = await _register_result(db, diff_raw, f"band_ratio_{bundle_id}", bundle_id)
    mask_index_id = None
    if mask_raw:
        mask_index_id = await _register_result(db, mask_raw, f"band_ratio_mask_{bundle_id}", bundle_id)

    return ChangeDetectResponse(
        diff_index_id=diff_index_id,
        mask_index_id=mask_index_id,
        method="band_ratio",
        change_pixel_count=result["change_pixel_count"],
        change_area_ratio=_calc_change_ratio(result["change_pixel_count"], diff_raw),
    )


@router.post("/index-diff", response_model=ChangeDetectResponse, summary="Index DifferenceChange Detection")
async def detect_index_diff(
    req: IndexDiffRequest,
    db: AsyncSession = Depends(get_db),
):
    path_t1_b1 = await _get_raster_path(db, req.index_id_t1_b1, "t1_b1")
    path_t1_b2 = await _get_raster_path(db, req.index_id_t1_b2, "t1_b2")
    path_t2_b1 = await _get_raster_path(db, req.index_id_t2_b1, "t2_b1")
    path_t2_b2 = await _get_raster_path(db, req.index_id_t2_b2, "t2_b2")

    bundle_id = f"change_idxdiff_{req.index_type}_{int(time.time())}"
    diff_raw = os.path.join(RAW_DIR, f"{bundle_id}_diff.tif")
    mask_raw = os.path.join(RAW_DIR, f"{bundle_id}_mask.tif") if req.output_mask else None

    result = index_diff(
        path_t1_b1=path_t1_b1,
        path_t1_b2=path_t1_b2,
        path_t2_b1=path_t2_b1,
        path_t2_b2=path_t2_b2,
        output_diff_path=diff_raw,
        output_mask_path=mask_raw,
        index_type=req.index_type,
        threshold=req.threshold,
        threshold_mode=req.threshold_mode,
    )

    diff_index_id = await _register_result(db, diff_raw, f"index_diff_{bundle_id}", bundle_id)
    mask_index_id = None
    if mask_raw:
        mask_index_id = await _register_result(db, mask_raw, f"index_diff_mask_{bundle_id}", bundle_id)

    return ChangeDetectResponse(
        diff_index_id=diff_index_id,
        mask_index_id=mask_index_id,
        method=f"index_diff_{req.index_type}",
        change_pixel_count=result["change_pixel_count"],
        change_area_ratio=_calc_change_ratio(result["change_pixel_count"], diff_raw),
    )
