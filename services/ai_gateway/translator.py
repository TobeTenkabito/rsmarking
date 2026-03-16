# services/ai_gateway/translator.py
import os
import json
import logging
from uuid import UUID
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from functions.common.snowflake_utils import get_next_index_id
from services.data_service.crud import RasterCRUD
from services.annotation_service.crud.feature import LayerCRUD

from services.ai_gateway.schema_validator import (
    AIRequestPayload,
    TaskMode,
    DataType,
    RasterModifiable,
    VectorModifiable
)

# 引入解耦出的模块
from services.ai_gateway.data_extractor import _extract_raster_data, _extract_vector_data
from services.ai_gateway.llm_engine import _build_system_prompt, call_llm_with_retry

load_dotenv()

MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-chat")
logger = logging.getLogger("ai_gateway.translator")
logger.info(f"[AI] 当前使用模型: {MODEL}, Key前缀: {os.getenv('DEEPSEEK_API_KEY', 'NOT FOUND')[:8]}")


async def process_ai_task(
        payload: AIRequestPayload,
        db: AsyncSession,
        model_name: str = MODEL
) -> Dict[str, Any]:
    """AI 网关的主处理流程（对外接口保持不变）"""
    logger.info(f"开始处理 AI 任务: Target={payload.target_id}, Mode={payload.mode}, Type={payload.data_type}")

    # 1. 提取原始上下文数据
    if payload.data_type == DataType.RASTER:
        context_data = await _extract_raster_data(db, int(payload.target_id))
        modifiable_schema = RasterModifiable.model_json_schema()
    else:
        context_data = await _extract_vector_data(db, str(payload.target_id))
        modifiable_schema = VectorModifiable.model_json_schema()

    original_json_str = context_data.model_dump_json(indent=2)

    # 2. 构建 Prompt
    system_prompt = _build_system_prompt(
        payload.mode,
        payload.data_type,
        payload.language,
        json.dumps(modifiable_schema, ensure_ascii=False)
    )
    user_prompt = (
        f"【原始数据上下文】\n{original_json_str}\n\n"
        f"【用户指令】\n{payload.user_prompt}\n\n"
        f"请使用 {payload.language.value} 语言进行回复。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # 3. 调用 AI
    result = await call_llm_with_retry(messages, model_name, payload.mode, payload.data_type)

    # 4. 分析模式直接返回
    if payload.mode == TaskMode.ANALYZE:
        return {
            "status": "success",
            "mode": "analyze",
            "report": result
        }

    # 5. 修改模式处理（数据库落地部分保持原有逻辑，不作改变）
    if payload.mode == TaskMode.MODIFY:
        validated_data = result
        modified_dict = validated_data.model_dump(exclude_none=True)

        if not modified_dict:
            logger.warning("[process_ai_task] AI 返回的可修改字段全为空，放弃写入")
            return {
                "status": "no_change",
                "mode": "modify",
                "message": "AI 未返回任何可修改字段"
            }

        logger.info(f"[process_ai_task] AI 修改内容: {modified_dict}")

        if payload.overwrite:
            if payload.data_type == DataType.RASTER:
                updated = await RasterCRUD.update_raster(db, int(payload.target_id), modified_dict)
                if not updated:
                    raise ValueError(f"覆盖失败：找不到 index_id={payload.target_id} 的栅格记录")
            else:
                layer_crud = LayerCRUD(db)
                updated = await layer_crud.update_layer(UUID(str(payload.target_id)), {"name": modified_dict.get("name")})
                if not updated:
                    raise ValueError(f"覆盖失败：找不到 id={payload.target_id} 的矢量图层")

            await db.commit()
            return {
                "status": "success", "mode": "modify", "action": "overwrite",
                "target_id": str(payload.target_id), "modified_data": modified_dict
            }
        else:
            if payload.data_type == DataType.RASTER:
                original = await RasterCRUD.get_raster_by_index_id(db, int(payload.target_id))
                if not original:
                    raise ValueError(f"新建失败：找不到 index_id={payload.target_id} 的栅格记录")

                new_name = modified_dict.get("name", original.file_name)
                if not new_name.endswith(".tif"):
                    new_name = f"{new_name}.tif"

                new_meta = {
                    "file_name": new_name, "index_id": get_next_index_id(), "bundle_id": original.bundle_id,
                    "file_path": original.file_path, "cog_path": original.cog_path, "crs": original.crs,
                    "bounds": original.bounds, "center": original.center, "width": original.width,
                    "height": original.height, "bands": original.bands, "data_type": original.data_type,
                    "resolution_x": original.resolution_x, "resolution_y": original.resolution_y,
                }
                new_raster = await RasterCRUD.create_raster(db, new_meta)
                await db.commit()
                return {
                    "status": "success", "mode": "modify", "action": "create_new",
                    "new_index_id": new_raster.index_id, "modified_data": modified_dict
                }
            else:
                layer_crud = LayerCRUD(db)
                original = await layer_crud.get_layer(UUID(str(payload.target_id)))
                if not original:
                    raise ValueError(f"新建失败：找不到 id={payload.target_id} 的矢量图层")

                new_layer = await layer_crud.create_layer(
                    project_id=original.project_id,
                    name=modified_dict.get("name", f"{original.name}_AI修正版"),
                    source_index_id=original.source_raster_index_id
                )
                await db.commit()
                return {
                    "status": "success", "mode": "modify", "action": "create_new",
                    "new_layer_id": str(new_layer.id), "modified_data": modified_dict
                }

    raise ValueError(f"未知的任务模式: {payload.mode}")