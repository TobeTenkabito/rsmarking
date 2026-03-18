import json
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_gateway.schema_validator import AIRequestPayload, TaskMode, DataType, RasterModifiable, VectorModifiable
from services.ai_gateway.data_extractor import _extract_raster_data, _extract_vector_data
from services.ai_gateway.llm_engine import _build_system_prompt, call_llm_with_retry

logger = logging.getLogger("ai_gateway.analyze_handler")


async def handle_analyze(payload: AIRequestPayload, db: AsyncSession, model_name: str) -> Dict[str, Any]:
    if payload.data_type == DataType.RASTER:
        context_data = await _extract_raster_data(db, int(payload.target_id))
        modifiable_schema = RasterModifiable.model_json_schema()
        valid_schema = None
    else:
        context_data = await _extract_vector_data(db, str(payload.target_id))
        modifiable_schema = VectorModifiable.model_json_schema()
        valid_schema = context_data.properties_schema
    original_json_str = context_data.model_dump_json(indent=2)
    system_prompt = _build_system_prompt(
        TaskMode.ANALYZE, payload.data_type, payload.language, json.dumps(modifiable_schema, ensure_ascii=False)
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
    result = await call_llm_with_retry(
        messages=messages,
        model_name=model_name,
        mode=TaskMode.ANALYZE,
        expected_type=payload.data_type,
        db=db,
        target_id=str(payload.target_id),
        context_schema=valid_schema
    )
    return {
        "status": "success",
        "mode": "analyze",
        "report": result
    }