import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_gateway.schema_validator import AIRequestPayload, TaskMode
from services.ai_gateway.analyze_handler import handle_analyze
from services.ai_gateway.modify_handler import handle_modify
from services.ai_gateway.context_builder import build_map_context
from services.ai_gateway.config import get_ai_model

logger = logging.getLogger("ai_gateway.translator")


async def process_ai_task(
    payload: AIRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> Dict[str, Any]:

    # 1. Build a map-context fragment and inject it into the payload for handlers.
    map_ctx_str = build_map_context(payload.map_context)

    # 3. Dispatch to the matching handler
    if payload.mode == TaskMode.ANALYZE:
        result = await handle_analyze(
            payload, db, vector_db, get_ai_model(),
            map_context_str=map_ctx_str,
        )
    else:
        result = await handle_modify(
            payload, db, vector_db, get_ai_model(),
            map_context_str=map_ctx_str,
        )

    return result
