import json
import logging
from typing import Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_gateway.schema_validator import (
    AIRequestPayload, TaskMode, DataType,
    RasterModifiable, VectorModifiable
)
from services.ai_gateway.data_extractor import _extract_raster_data, _extract_vector_data
from services.ai_gateway.llm_engine import _build_system_prompt, call_llm_with_retry

logger = logging.getLogger("ai_gateway.analyze_handler")


async def handle_analyze(
    payload: AIRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
    model_name: str,
    # ── 新增参数（均有默认值，向后兼容旧调用方） ──
    history: List[Dict[str, Any]] = None,
    map_context_str: str = "",
) -> Dict[str, Any]:

    history = history or []

    # 1. 提取数据上下文
    if payload.data_type == DataType.RASTER:
        context_data = await _extract_raster_data(db, int(payload.target_id))
        modifiable_schema = RasterModifiable.model_json_schema()
        valid_schema = None
    else:
        context_data = await _extract_vector_data(vector_db, str(payload.target_id))
        modifiable_schema = VectorModifiable.model_json_schema()
        valid_schema = context_data.properties_schema

    original_json_str = context_data.model_dump_json(indent=2)

    # 2. 构建 system prompt
    system_prompt = _build_system_prompt(
        TaskMode.ANALYZE,
        payload.data_type,
        payload.language,
        json.dumps(modifiable_schema, ensure_ascii=False),
    )

    # 3. 构建本轮 user_prompt
    #    map_context_str 非空时拼接在数据上下文之前
    map_section = f"{map_context_str}\n\n" if map_context_str else ""
    user_prompt = (
        f"{map_section}"
        f"【原始数据上下文】\n{original_json_str}\n\n"
        f"【用户指令】\n{payload.user_prompt}\n\n"
        f"请使用 {payload.language.value} 语言进行回复。"
    )

    # 4. 拼接完整 messages：system + 历史记忆 + 本轮 user
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_prompt}]
    )

    # 5. 调用 LLM
    result = await call_llm_with_retry(
        messages=messages,
        model_name=model_name,
        mode=TaskMode.ANALYZE,
        expected_type=payload.data_type,
        db=db,
        target_id=str(payload.target_id),
        context_schema=valid_schema,
    )

    return {
        "status": "success",
        "mode": "analyze",
        "report": result,
    }
