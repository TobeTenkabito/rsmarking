import httpx
import os
import uuid
import logging
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from services.data_service.crud import RasterCRUD
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
    input_filenames = []
    for r_id in raster_ids:
        raster = await RasterCRUD.get_raster_by_index_id(db, r_id)
        if not raster:
            raise HTTPException(status_code=404, detail=f"影像 ID {r_id} 在库中未找到")
        # 只需要文件名，executor 服务会根据其 config 拼接路径
        input_filenames.append(os.path.basename(raster.file_path))

    # 生成本次任务的唯一标识
    task_id = str(uuid.uuid4())
    prefix = "script"

    # 预定义输出路径（需与 executor 配置的宿主机目录一致）
    # 让沙箱直接把结果写到 UPLOAD_DIR (即 storage/raw)，模拟上传的文件
    raw_output_filename = f"{task_id}_{prefix}_raw.tif"

    # 2. 调用沙箱执行服务
    # 注意：这里的 timeout 需要设置得足够长，因为遥感运算耗时较久
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            payload = {
                "script_content": script,
                "input_filenames": input_filenames,
                "output_filename": raw_output_filename
            }
            response = await client.post(EXECUTOR_URL, json=payload)
            response.raise_for_status()
            res_data = response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="无法连接到执行服务沙箱，请检查服务是否启动")
        except Exception as e:
            logger.error(f"沙箱调用异常: {str(e)}")
            raise HTTPException(status_code=500, detail=f"执行服务故障: {str(e)}")

    if res_data.get("status") != "success":
        # 如果沙箱内部报错（如脚本语法错误、GDAL计算错误），提取其 logs 返回给前端查看
        return {
            "status": "error",
            "message": "沙箱执行失败",
            "logs": res_data.get("logs", "未知错误")
        }

    # 3. 后处理：将沙箱生成的 raw 文件转换为 COG
    # 此时文件已存在于 /storage/raw/{raw_output_filename}
    tmp_path = os.path.join(UPLOAD_DIR, raw_output_filename)
    cog_filename = f"{task_id}_{prefix}.tif"
    cog_path = os.path.join(COG_DIR, cog_filename)

    if not os.path.exists(tmp_path):
        raise HTTPException(status_code=500, detail="沙箱报告成功但未找到生成的影像文件")

    try:
        # 调用 processor 执行标准转换
        RasterProcessor.convert_to_cog(tmp_path, cog_path)

        # 4. 结果入库：复用 db_ops 中的 save_to_db，自动提取 CRS、Bounds 等元数据
        db_res = await save_to_db(
            db=db,
            task_id=task_id,
            new_name=output_name,
            tmp_path=tmp_path,
            cog_filename=cog_filename,
            cog_path=cog_path,
            prefix=prefix,
            bands_count=1  # 脚本默认输出单波段，save_to_db 内部会自动重新探测
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