import os
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from services.ai_gateway.schema_validator import AIRequestPayload, TaskMode
from services.ai_gateway.analyze_handler import handle_analyze
from services.ai_gateway.modify_handler import handle_modify

load_dotenv()

MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-chat")
logger = logging.getLogger("ai_gateway.translator")
logger.info(f"[AI] 当前使用模型: {MODEL}, Key前缀: {os.getenv('DEEPSEEK_API_KEY', 'NOT FOUND')[:8]}")


async def process_ai_task(
        payload: AIRequestPayload,
        db: AsyncSession,
        vector_db: AsyncSession,        # ← 新增
        model_name: str = MODEL
) -> Dict[str, Any]:
    logger.info(f"开始路由 AI 任务: Target={payload.target_id}, Mode={payload.mode}, Type={payload.data_type}")

    if payload.mode == TaskMode.ANALYZE:
        return await handle_analyze(payload, db, vector_db, model_name)   # ← 透传
    elif payload.mode == TaskMode.MODIFY:
        return await handle_modify(payload, db, vector_db, model_name)    # ← 透传
    else:
        raise ValueError(f"未知的任务模式: {payload.mode}")