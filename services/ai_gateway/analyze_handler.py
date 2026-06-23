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
    map_context_str: str = "",
) -> Dict[str, Any]:


    # 1. Extract data context
    if payload.data_type == DataType.RASTER:
        context_data = await _extract_raster_data(db, int(payload.target_id))
        modifiable_schema = RasterModifiable.model_json_schema()
        valid_schema = None
    else:
        context_data = await _extract_vector_data(vector_db, str(payload.target_id))
        modifiable_schema = VectorModifiable.model_json_schema()
        valid_schema = context_data.properties_schema

    original_json_str = context_data.model_dump_json(indent=2)

    # 2. Build the system prompt
    system_prompt = _build_system_prompt(
        TaskMode.ANALYZE,
        payload.data_type,
        payload.language,
        json.dumps(modifiable_schema, ensure_ascii=False),
    )

    # 3. Build the user prompt for this turn
    #    When map_context_str is not empty, prepend it before the data context
    map_section = f"{map_context_str}\n\n" if map_context_str else ""
    user_prompt = (
        f"{map_section}"
        f"[Original Data Context]\n{original_json_str}\n\n"
        f"[User Instruction]\n{payload.user_prompt}\n\n"
        f"Respond in {payload.language.value}."
    )

    # 4. Build complete messages: system + conversation memory + current user prompt
    messages = (
        [{"role": "system", "content": system_prompt}]
        + [{"role": "user", "content": user_prompt}]
    )

    # 5. Call the LLM
    result = await call_llm_with_retry(
        messages=messages,
        model_name=model_name,
        mode=TaskMode.ANALYZE,
        expected_type=payload.data_type,
        db=db,
        target_id=str(payload.target_id),
        context_schema=valid_schema,
    )

    response = {
        "status": "success",
        "mode": "analyze",
        "report": result,
    }
    try:
        from services.ai_gateway.artifacts import create_document_artifact

        artifact = create_document_artifact(
            f"ai-analysis-{payload.data_type.value}-{payload.target_id}.md",
            str(result),
            "md",
        )
        response["artifact"] = artifact
        response["artifacts"] = [artifact]
        response["file_url"] = artifact["download_url"]
    except Exception as exc:
        logger.warning("[analyze] could not persist downloadable report: %s", exc)
    return response
