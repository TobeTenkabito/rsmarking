import os
import shutil
import uuid
import logging


from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends, Form, Request
from fastapi.responses import FileResponse
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


from services.data_service.database import get_db
import services.data_service.models as models
from services.data_service.processor import RasterProcessor
from services.data_service.crud import RasterCRUD
import services.data_service.db_ops as db_ops


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")
CLIENT_DIR = os.path.join(BASE_DIR, "client")

logger = logging.getLogger("data_service.control")
router = APIRouter()


@router.get("/")
async def read_index():
    index_path = os.path.join(CLIENT_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend index.html not found"}


@router.post("/upload")
async def upload_raster(
        file: UploadFile = File(...),
        bundle_id: str = Form(None),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: AsyncSession = Depends(get_db)
):
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    raw_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    cog_filename = f"{file_id}.tif"
    cog_path = os.path.join(COG_DIR, cog_filename)

    try:
        with open(raw_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        metadata = RasterProcessor.extract_metadata(raw_path)
        result = await db_ops.save_to_db(
            db, file_id, file.filename, raw_path, cog_filename, cog_path, "upload",
            bands_count=metadata.get("bands", 1),
            metadata_source=raw_path
        )
        background_tasks.add_task(db_ops.run_conversion, raw_path, cog_path)
        return {"id": result["id"], "status": "processing", "metadata": metadata}
    except Exception as e:
        logger.error(f"上传失败: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge-bands")
async def merge_bands(
        raster_ids: str = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    try:
        ids = [int(i) for i in raster_ids.split(',')]
        input_paths = []
        for rid in ids:
            result = await db.execute(select(models.RasterMetadata).where(models.RasterMetadata.index_id == rid))
            r = result.scalars().first()
            if r: input_paths.append(r.file_path)

        if not input_paths:
            raise HTTPException(status_code=400, detail="No valid band path found")

        upload_id = str(uuid.uuid4())
        tmp_tiff = os.path.join(UPLOAD_DIR, f"{upload_id}_merged.tif")
        cog_filename = f"{upload_id}_{new_name}.tif" if not new_name.endswith('.tif') else f"{upload_id}_{new_name}"
        cog_output = os.path.join(COG_DIR, cog_filename)

        RasterProcessor.merge_bands(input_paths, tmp_tiff)
        RasterProcessor.convert_to_cog(tmp_tiff, cog_output)

        return await db_ops.save_to_db(db, upload_id, new_name, tmp_tiff, cog_filename, cog_output, "merged",
                                       bands_count=len(input_paths))
    except Exception as e:
        logger.error(f"合成任务失败: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-ndvi")
async def calculate_ndvi_api(
        red_id: int = Form(...),
        nir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await db_ops.process_index_task(db, [red_id, nir_id], new_name, "ndvi", RasterProcessor.calculate_ndvi)


@router.post("/calculate-ndwi")
async def calculate_ndwi_api(
        green_id: int = Form(...),
        nir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await db_ops.process_index_task(db, [green_id, nir_id], new_name, "ndwi", RasterProcessor.calculate_ndwi)


@router.post("/calculate-ndbi")
async def calculate_ndbi_api(
        swir_id: int = Form(...),
        nir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await db_ops.process_index_task(db, [swir_id, nir_id], new_name, "ndbi", RasterProcessor.calculate_ndbi)


@router.post("/calculate-mndwi")
async def calculate_mndwi_api(
        green_id: int = Form(...),
        swir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    return await db_ops.process_index_task(db, [green_id, swir_id], new_name, "mndwi", RasterProcessor.calculate_mndwi)


@router.post("/extract-vegetation")
async def extract_vegetation_api(
        request: Request,
        new_name: str = Form(...),
        threshold: float = Form(None),
        mode: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    band_ids = await db_ops.get_dynamic_band_ids(request)
    if not band_ids:
        raise HTTPException(status_code=400, detail="No band IDs provided.")
    return await db_ops.process_extraction_task(
        db, band_ids, new_name, "veg",
        RasterProcessor.run_vegetation_extraction,
        threshold=threshold,
        mode=mode
    )


@router.post("/extract-water")
async def extract_water_api(
    request: Request,
    new_name: str = Form(...),
    threshold: float = Form(None),
    mode: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    band_ids = await db_ops.get_dynamic_band_ids(request)
    if not band_ids:
        raise HTTPException(status_code=400, detail="No band IDs provided.")
    return await db_ops.process_extraction_task(
        db,
        band_ids,
        new_name,
        "water",
        RasterProcessor.run_water_extraction,
        threshold=threshold,
        mode=mode
    )


@router.post("/extract-buildings")
async def extract_buildings_api(
        request: Request,
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    band_ids = await db_ops.get_dynamic_band_ids(request)
    if not band_ids:
        raise HTTPException(status_code=400, detail="No band IDs provided.")
    return await db_ops.process_extraction_task(
        db, band_ids, new_name, "building",
        RasterProcessor.run_building_extraction,
        has_optional_red=(len(band_ids) > 2)
    )


@router.post("/extract-clouds")
async def extract_clouds_api(
        request: Request,
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    band_ids = await db_ops.get_dynamic_band_ids(request)
    if not band_ids:
        raise HTTPException(status_code=400, detail="No band IDs provided.")
    return await db_ops.process_extraction_task(
        db, band_ids, new_name, "cloud",
        RasterProcessor.run_cloud_extraction,
        has_optional_swir=(len(band_ids) > 1)
    )

@router.get("/list")
async def list_rasters(db: AsyncSession = Depends(get_db)):
    return await RasterCRUD.get_all_rasters(db)


@router.delete("/raster/{raster_id}")
async def delete_raster(raster_id: int, db: AsyncSession = Depends(get_db)):
    success = await RasterCRUD.delete_raster(db, raster_id)
    if not success:
        raise HTTPException(status_code=404, detail="Image does not exist")
    return {"status": "success"}


@router.get("/debug/clear-db")
async def clear_database(db: AsyncSession = Depends(get_db)):
    await RasterCRUD.clear_all_rasters(db)
    return {"message": "Database cleared"}
