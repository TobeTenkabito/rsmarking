import logging
import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.database import get_db
from services.data_service.processor import RasterProcessor
from services.data_service.raster_statistics import compute_raster_statistics


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
CLIENT_DIR = os.path.join(BASE_DIR, "client")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")

logger = logging.getLogger("data_service.raster")
router = APIRouter()


def resolve_raster_file_path(path: str | None) -> str | None:
    if not path:
        return None
    if os.path.exists(path):
        return path
    if path.startswith("/data/"):
        local = os.path.join(COG_DIR, os.path.basename(path))
        if os.path.exists(local):
            return local
    return None


@router.get("/")
async def read_index():
    index_path = os.path.join(CLIENT_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend index.html not found"}


@router.get("/list")
async def list_rasters(db: AsyncSession = Depends(get_db)):
    return await RasterCRUD.get_all_rasters(db)


@router.delete("/raster/{raster_id}")
async def delete_raster(raster_id: int, db: AsyncSession = Depends(get_db)):
    success = await RasterCRUD.delete_raster(db, raster_id)
    if not success:
        raise HTTPException(status_code=404, detail="Raster not found")
    return {"status": "success"}


@router.get("/debug/clear-db")
async def clear_database(db: AsyncSession = Depends(get_db)):
    await RasterCRUD.clear_all_rasters(db)
    return {"message": "Database cleared"}


@router.post("/raster-calculator")
async def raster_calculator_api(
    request: Request,
    expression: str = Form(...),
    new_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    form_data = await request.form()
    var_mapping = {}
    for key, value in form_data.items():
        if key.startswith("var_"):
            var_name = key[4:]
            var_mapping[var_name] = int(value)

    if not var_mapping:
        raise HTTPException(
            status_code=400,
            detail="No raster variables were provided for the calculation",
        )

    return await db_ops.process_calculator_task(
        db, var_mapping, expression, new_name, "calc"
    )


@router.get("/raster/{raster_id}/spectrum")
async def query_spectrum(
    raster_id: int,
    lng: float,
    lat: float,
    db: AsyncSession = Depends(get_db),
):
    record = await RasterCRUD.get_raster_by_index_id(db, raster_id)
    if not record:
        raise HTTPException(status_code=404, detail="Raster not found")

    file_path = resolve_raster_file_path(record.cog_path) or resolve_raster_file_path(record.file_path)
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail=f"Raster file not found | cog_path={record.cog_path} | file_path={record.file_path}",
        )

    try:
        return RasterProcessor.query_spectrum(file_path, lng, lat)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Spectrum query failed: {exc}")
        raise HTTPException(status_code=500, detail="Spectrum query failed") from exc


@router.get("/raster/{raster_id}/statistics")
async def raster_statistics(
    raster_id: int,
    bins: int = 32,
    max_size: int = 768,
    bands: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    record = await RasterCRUD.get_raster_by_index_id(db, raster_id)
    if not record:
        raise HTTPException(status_code=404, detail="Raster not found")

    file_path = resolve_raster_file_path(record.cog_path) or resolve_raster_file_path(record.file_path)
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail=f"Raster file not found | cog_path={record.cog_path} | file_path={record.file_path}",
        )

    band_indices = None
    if bands:
        try:
            band_indices = [int(value.strip()) for value in bands.split(",") if value.strip()]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid bands parameter") from exc

    try:
        stats = compute_raster_statistics(
            file_path,
            bins=bins,
            max_size=max_size,
            band_indices=band_indices,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Raster statistics failed: {exc}")
        raise HTTPException(status_code=500, detail="Raster statistics failed") from exc

    stats.update(
        {
            "raster_id": record.index_id,
            "record_id": record.id,
            "file_name": record.file_name,
        }
    )
    return stats
