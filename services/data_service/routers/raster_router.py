import os
import logging

from fastapi import APIRouter, HTTPException, Depends, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
import services.data_service.db_ops as db_ops
from services.data_service.crud.raster_crud import RasterCRUD

# Constants
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
CLIENT_DIR = os.path.join(BASE_DIR, "client")

logger = logging.getLogger("data_service.raster")
router = APIRouter()


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
        raise HTTPException(status_code=404, detail="影像不存在")
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
        db: AsyncSession = Depends(get_db)
):
    """
    栅格计算器。
    表单额外字段 var_A=<raster_id>, var_B=<raster_id> … 动态映射变量。
    expression 示例: "(A - B) / (A + B)"
    """
    form_data = await request.form()
    var_mapping = {}
    for key, value in form_data.items():
        if key.startswith("var_"):
            var_name = key[4:]
            var_mapping[var_name] = int(value)

    if not var_mapping:
        raise HTTPException(status_code=400, detail="未提供参与计算的变量与图层映射")

    return await db_ops.process_calculator_task(
        db, var_mapping, expression, new_name, "calc"
    )
