import os
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from services.ai_gateway.schema_validator import AIRequestPayload, TaskMode
from services.ai_gateway.analyze_handler import handle_analyze
from services.ai_gateway.modify_handler import handle_modify
from services.ai_gateway.context_builder import build_map_context

load_dotenv()

MODEL = os.getenv("AI_MODEL")
logger = logging.getLogger("ai_gateway.translator")
logger.info(f"[AI] 当前使用模型: {MODEL}")


async def process_ai_task(
    payload: AIRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> Dict[str, Any]:

    # 1. 构建地图上下文片段（注入 payload，供 handler 使用）
    map_ctx_str = build_map_context(payload.map_context)

    # 3. 分发到对应 handler
    if payload.mode == TaskMode.ANALYZE:
        result = await handle_analyze(
            payload, db, vector_db, MODEL,
            map_context_str=map_ctx_str,
        )
    else:
        result = await handle_modify(
            payload, db, vector_db, MODEL,
            map_context_str=map_ctx_str,
        )

    return result
