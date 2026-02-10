import sys
import os
import shutil
import uuid
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("data_service_init")
from contextlib import asynccontextmanager
from typing import List


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

from functions.common.snowflake_utils import get_next_index_id

# 导入内部组件 (确保路径正确)
from services.data_service.database import get_db, engine, Base
import services.data_service.models as models
from services.data_service.processor import RasterProcessor
from services.data_service.crud import RasterCRUD


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("data_service")


UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")
CLIENT_DIR = os.path.join(BASE_DIR, "client")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COG_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== DATA SERVICE STARTUP BEGIN ===")
    logger.info(f"[DB] engine.url = {engine.url}")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT current_database()"))
        db_name = result.scalar()

        result = await conn.execute(text("SELECT current_schema()"))
        schema = result.scalar()

        logger.info(f"[DB] database = {db_name}")
        logger.info(f"[DB] schema = {schema}")
        logger.info(f"[DB] Base.metadata.tables = {list(Base.metadata.tables.keys())}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """))
        tables = [r[0] for r in result.fetchall()]
        logger.info(f"[DB] tables in public schema: {tables}")

    logger.info("=== DATA SERVICE STARTUP OK ===")
    yield


app = FastAPI(lifespan=lifespan)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/data", StaticFiles(directory=os.path.abspath(COG_DIR)), name="cog_data")


if os.path.exists(CLIENT_DIR):
    app.mount("/client", StaticFiles(directory=CLIENT_DIR), name="client")
    logger.info("已成功挂载 /client 路径")


def run_conversion(input_path: str, output_path: str):
    try:
        RasterProcessor.convert_to_cog(input_path, output_path)
    except Exception as e:
        logger.error(f"COG 转换失败: {str(e)}")


@app.get("/")
async def read_index():
    index_path = os.path.join(CLIENT_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    logger.error(f"未找到 index.html，检查路径: {index_path}")
    return {
        "error": "Frontend index.html not found",
        "expected_path": index_path,
        "base_dir": BASE_DIR
    }


@app.post("/upload")
async def upload_raster(
        file: UploadFile = File(...),
        bundle_id: str = Form(None),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: AsyncSession = Depends(get_db)
):
    file_id = str(uuid.uuid4())
    raw_path = os.path.join(UPLOAD_DIR, f"{file_id}{os.path.splitext(file.filename)[1]}")
    cog_filename = f"{file_id}.tif"
    cog_path = os.path.join(COG_DIR, cog_filename)

    try:
        with open(raw_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        metadata = RasterProcessor.extract_metadata(raw_path)
        db_data = metadata.copy()
        db_data.update({
            "bundle_id": bundle_id or str(uuid.uuid4()),
            "index_id": get_next_index_id(),
            "file_path": raw_path,
            "cog_path": f"/data/{cog_filename}"
        })

        db_record = await RasterCRUD.create_raster(db, db_data)
        await db.commit()
        background_tasks.add_task(run_conversion, raw_path, cog_path)

        return {"id": db_record.id, "status": "processing", "metadata": metadata}
    except Exception as e:
        logger.error(f"上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/merge-bands")
async def merge_bands(
        raster_ids: str = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    try:
        ids = [int(i) for i in raster_ids.split(',')]
        input_paths = []
        for rid in ids:
            result = await db.execute(select(models.RasterMetadata).where(models.RasterMetadata.id == rid))
            r = result.scalars().first()
            if r: input_paths.append(r.file_path)

        if not input_paths:
            raise HTTPException(status_code=400, detail="未找到有效波段路径")

        upload_id = str(uuid.uuid4())
        tmp_tiff = os.path.join(UPLOAD_DIR, f"{upload_id}_merged.tif")
        cog_filename = f"{upload_id}_{new_name}.tif" if not new_name.endswith('.tif') else f"{upload_id}_{new_name}"
        cog_output = os.path.join(COG_DIR, cog_filename)

        # 执行合成逻辑 (内部调用 GDAL 或 Rasterio)
        RasterProcessor.merge_bands(input_paths, tmp_tiff)
        # 立即转换为 COG 以供前端显示
        RasterProcessor.convert_to_cog(tmp_tiff, cog_output)

        # 提取入库元数据
        metadata = RasterProcessor.extract_metadata(cog_output)
        db_data = {
            "file_name": new_name,
            "file_path": tmp_tiff,
            "cog_path": f"/data/{cog_filename}",
            "bundle_id": f"merged_{upload_id[:8]}",
            "index_id": get_next_index_id(),
            "crs": metadata.get("crs"),
            "bounds": metadata.get("bounds"),
            "center": metadata.get("center"),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "bands": len(input_paths),
            "data_type": metadata.get("data_type"),
            "resolution_x": metadata.get("resolution")[0] if metadata.get("resolution") else None,
            "resolution_y": metadata.get("resolution")[1] if metadata.get("resolution") else None
        }

        new_record = await RasterCRUD.create_raster(db, db_data)
        await db.commit()

        return {"status": "success", "id": new_record.id, "cog_url": db_data["cog_path"]}

    except Exception as e:
        logger.error(f"合成任务失败: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate-ndvi")
async def calculate_ndvi_api(
        red_id: int = Form(...),
        nir_id: int = Form(...),
        new_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    try:
        res_red = await db.execute(select(models.RasterMetadata).where(models.RasterMetadata.id == red_id))
        res_nir = await db.execute(select(models.RasterMetadata).where(models.RasterMetadata.id == nir_id))
        red_r = res_red.scalar_one_or_none()
        nir_r = res_nir.scalar_one_or_none()

        if not red_r or not nir_r:
            raise HTTPException(status_code=404, detail="红光或近红外波段不存在")

        task_id = str(uuid.uuid4())
        tmp_path = os.path.join(UPLOAD_DIR, f"{task_id}_ndvi_raw.tif")
        cog_filename = f"{task_id}_ndvi.tif"
        cog_path = os.path.join(COG_DIR, cog_filename)
        RasterProcessor.calculate_ndvi(red_r.file_path, nir_r.file_path, tmp_path)
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        metadata = RasterProcessor.extract_metadata(cog_path)
        db_data = {
            "file_name": new_name if new_name.endswith(".tif") else f"{new_name}.tif",
            "file_path": tmp_path,
            "cog_path": f"/data/{cog_filename}",
            "bundle_id": f"ndvi_{task_id[:8]}",
            "index_id": get_next_index_id(),
            "crs": metadata.get("crs"),
            "bounds": metadata.get("bounds"),
            "center": metadata.get("center"),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "bands": 1,
            "data_type": metadata.get("data_type"),
            "resolution_x": metadata.get("resolution")[0] if metadata.get("resolution") else None,
            "resolution_y": metadata.get("resolution")[1] if metadata.get("resolution") else None
        }

        new_record = await RasterCRUD.create_raster(db, db_data)
        await db.commit()

        return {"status": "success", "id": new_record.id}
    except Exception as e:
        logger.error(f"NDVI 计算失败: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/list")
async def list_rasters(db: AsyncSession = Depends(get_db)):
    return await RasterCRUD.get_all_rasters(db)


@app.delete("/raster/{raster_id}")
async def delete_raster(raster_id: int, db: AsyncSession = Depends(get_db)):
    success = await RasterCRUD.delete_raster(db, raster_id)
    if not success:
        raise HTTPException(status_code=404, detail="影像不存在")
    return {"status": "success"}


@app.get("/debug/clear-db")
async def clear_database(db: AsyncSession = Depends(get_db)):
    await RasterCRUD.clear_all_rasters(db)
    return {"message": "Database cleared"}


@app.on_event("startup")
async def debug_db():
    print(f"SERVICE DATABASE URL: {engine.url}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
