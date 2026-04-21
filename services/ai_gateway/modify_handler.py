import json
import logging
from uuid import UUID
from typing import Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from functions.common.snowflake_utils import get_next_index_id
from services.data_service.crud.raster_crud import RasterCRUD
from services.annotation_service.crud.layer_crud import LayerCRUD
from services.ai_gateway.schema_validator import (
    AIRequestPayload, TaskMode, DataType,
    RasterModifiable, VectorModifiable
)
from services.ai_gateway.data_extractor import _extract_raster_data, _extract_vector_data
from services.ai_gateway.llm_engine import _build_system_prompt, call_llm_with_retry

logger = logging.getLogger("ai_gateway.modify_handler")


async def handle_modify(
    payload: AIRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
    model_name: str,
    map_context_str: str = "",
) -> Dict[str, Any]:

    # 1. 提取数据上下文
    if payload.data_type == DataType.RASTER:
        context_data = await _extract_raster_data(db, int(payload.target_id))
        modifiable_schema = RasterModifiable.model_json_schema()
    else:
        context_data = await _extract_vector_data(vector_db, str(payload.target_id))
        modifiable_schema = VectorModifiable.model_json_schema()

    original_json_str = context_data.model_dump_json(indent=2)

    # 2. 构建 system prompt
    system_prompt = _build_system_prompt(
        TaskMode.MODIFY,
        payload.data_type,
        payload.language,
        json.dumps(modifiable_schema, ensure_ascii=False),
    )

    # 3. 构建本轮 user_prompt
    map_section = f"{map_context_str}\n\n" if map_context_str else ""
    user_prompt = (
        f"{map_section}"
        f"【原始数据上下文】\n{original_json_str}\n\n"
        f"【用户指令】\n{payload.user_prompt}\n\n"
        f"请使用 {payload.language.value} 语言进行回复。"
    )

    # 4. 拼接完整 messages：system + 历史记忆 + 本轮 user
    #    注意：MODIFY 模式下历史记忆仅供 LLM 理解上下文，
    #    最终写库依据的是本轮 validated_data，不受历史影响。
    messages = (
        [{"role": "system", "content": system_prompt}]
        + [{"role": "user", "content": user_prompt}]
    )

    # 5. 调用 LLM 并校验输出
    validated_data = await call_llm_with_retry(
        messages, model_name, TaskMode.MODIFY, payload.data_type
    )
    modified_dict = validated_data.model_dump(exclude_none=True)

    if not modified_dict:
        logger.warning("[handle_modify] AI 返回的可修改字段全为空，放弃写入")
        return {
            "status": "no_change",
            "mode": "modify",
            "message": "AI 未返回任何可修改字段",
        }

    logger.info(f"[handle_modify] AI 修改内容: {modified_dict}")

    # 6. 写库（overwrite 覆盖 / 否则新建副本）
    if payload.overwrite:
        if payload.data_type == DataType.RASTER:
            updated = await RasterCRUD.update_raster(
                db, int(payload.target_id), modified_dict
            )
            if not updated:
                raise ValueError(f"覆盖失败：找不到 index_id={payload.target_id} 的栅格")
            await db.commit()
        else:
            layer_crud = LayerCRUD(vector_db)
            updated = await layer_crud.update_layer(
                UUID(str(payload.target_id)),
                {"name": modified_dict.get("name")},
            )
            if not updated:
                raise ValueError(f"覆盖失败：找不到 id={payload.target_id} 的矢量图层")
            await vector_db.commit()

        return {
            "status": "success",
            "mode": "modify",
            "action": "overwrite",
            "modified_data": modified_dict,
        }

    else:
        if payload.data_type == DataType.RASTER:
            original = await RasterCRUD.get_raster_by_index_id(
                db, int(payload.target_id)
            )
            if not original:
                raise ValueError(f"新建失败：找不到 index_id={payload.target_id} 的栅格")

            new_name = modified_dict.get("name", original.file_name)
            if not new_name.endswith(".tif"):
                new_name = f"{new_name}.tif"

            new_meta = {
                "file_name":    new_name,
                "index_id":     get_next_index_id(),
                "bundle_id":    original.bundle_id,
                "file_path":    original.file_path,
                "cog_path":     original.cog_path,
                "crs":          original.crs,
                "bounds":       original.bounds,
                "center":       original.center,
                "width":        original.width,
                "height":       original.height,
                "bands":        original.bands,
                "data_type":    original.data_type,
                "resolution_x": original.resolution_x,
                "resolution_y": original.resolution_y,
            }
            new_raster = await RasterCRUD.create_raster(db, new_meta)
            await db.commit()
            return {
                "status":       "success",
                "mode":         "modify",
                "action":       "create_new",
                "new_index_id": new_raster.index_id,
                "modified_data": modified_dict,
            }

        else:
            layer_crud = LayerCRUD(vector_db)
            original = await layer_crud.get_layer(UUID(str(payload.target_id)))
            if not original:
                raise ValueError(f"新建失败：找不到 id={payload.target_id} 的矢量图层")

            new_name = modified_dict.get("name", original.name)
            new_layer = await layer_crud.create_layer(
                project_id=original.project_id,
                name=new_name,
                source_index_id=original.source_raster_index_id,
            )
            await vector_db.commit()
            return {
                "status":       "success",
                "mode":         "modify",
                "action":       "create_new",
                "new_layer_id": str(new_layer.id),
                "modified_data": modified_dict,
            }
