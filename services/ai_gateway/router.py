import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
from services.annotation_service.database import get_db as get_vector_db

from .schema_validator import AIRequestPayload
from .translator import process_ai_task

import os
MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-chat")

logger = logging.getLogger("ai_gateway.router")

router = APIRouter(
    prefix="/ai",
    tags=["AI Gateway - 智能空间数据网关"]
)


@router.post("/process", summary="处理 AI 空间数据任务 (分析/修改)")
async def handle_ai_task(
    payload: AIRequestPayload,
    db: AsyncSession = Depends(get_db),
    vector_db: AsyncSession = Depends(get_vector_db),
):
    try:
        return await process_ai_task(payload, db, vector_db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"[router] /process 异常: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI 处理失败")
