import httpx
import os
import uuid
import logging
from typing import List, Dict, Any
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.db_ops import save_to_db, UPLOAD_DIR, COG_DIR
from services.data_service.processor import RasterProcessor

logger = logging.getLogger("data_service.executor_bridge")

# 执行服务的内部通信地址
EXECUTOR_URL = "http://localhost:8004/execute"


async def dispatch_user_script(db: AsyncSession, script: str, raster_ids: list[int], output_name: str):
    """
    中转站核心逻辑：
    1. 转换 ID 为物理路径
    2. 调用外部沙箱执行计算
    3. 捕获输出文件并进行 COG 转换
    4. 自动解析元数据并持久化到数据库
    """
    # 1. 准备输入：将数据库 ID 映射为宿主机物理文件名
    input_files_payload = []
    for r_id in raster_ids:
        raster = await RasterCRUD.get_raster_by_index_id(db, r_id)
        if not raster:
            raise HTTPException(status_code=404, detail=f"影像 ID {r_id} 未找到")
        input_files_payload.append({
            "path": raster.file_path,
            "name": os.path.basename(raster.file_path)
        })

    task_id = str(uuid.uuid4())
    prefix = "script"
    raw_output_filename = f"{task_id}_{prefix}_raw.tif"

    # 2. 调用沙箱执行服务
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            payload = {
                "script_id": task_id,
                "script": script,
                "input_files": input_files_payload,
                "output_name": raw_output_filename
            }
            response = await client.post(EXECUTOR_URL, json=payload)
            response.raise_for_status()
            res_data = response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="无法连接到执行服务沙箱")
        except Exception as e:
            logger.error(f"沙箱调用异常: {str(e)}")
            raise HTTPException(status_code=500, detail=f"执行服务故障: {str(e)}")

    if res_data.get("status") != "success":
        return {
            "status": "error",
            "message": "沙箱执行失败",
            "logs": res_data.get("logs", "未知错误")
        }

    # 3. 后处理：转换 COG
    tmp_path = os.path.join(UPLOAD_DIR, raw_output_filename)
    cog_filename = f"{task_id}_{prefix}.tif"
    cog_path = os.path.join(COG_DIR, cog_filename)

    if not os.path.exists(tmp_path):
        raise HTTPException(status_code=500, detail="未找到生成的影像文件")

    try:
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        # 4. 结果入库
        db_res = await save_to_db(
            db=db,
            task_id=task_id,
            new_name=output_name,
            tmp_path=tmp_path,
            cog_filename=cog_filename,
            cog_path=cog_path,
            prefix=prefix,
            bands_count=1
        )

        return {
            "status": "success",
            "id": db_res.get("id"),
            "cog_url": db_res.get("cog_url"),
            "logs": res_data.get("logs", "")
        }

    except Exception as e:
        logger.error(f"脚本结果后处理失败: {str(e)}")
        if os.path.exists(tmp_path): os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"元数据入库失败: {str(e)}")
