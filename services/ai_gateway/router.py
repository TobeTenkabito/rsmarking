import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
from services.annotation_service.database import get_db as get_vector_db

from .schema_validator import AIRequestPayload
from .translator import process_ai_task
from .streaming_handler import handle_stream
from .feedback_collector import FeedbackPayload, collect_feedback, get_feedback_store
from .memory.session_memory import get_session_store

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


@router.post("/stream", summary="流式 AI 分析（SSE，仅支持 ANALYZE 模式）")
async def handle_ai_stream(
    payload: AIRequestPayload,
    db: AsyncSession = Depends(get_db),
    vector_db: AsyncSession = Depends(get_vector_db),
):
    """
    返回 text/event-stream，前端通过 EventSource 或 fetch+ReadableStream 消费。
    每帧格式：data: {"type": "token"|"done"|"error", "content": "..."}
    """
    try:
        session_store = get_session_store()
        return await handle_stream(payload, db, vector_db, MODEL, session_store)
    except Exception as e:
        logger.error(f"[router] /stream 异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="流式处理失败")


@router.post("/feedback", summary="提交 AI 结果反馈")
async def submit_feedback(payload: FeedbackPayload):
    """
    前端在用户点击👍/👎后调用，记录对 AI 输出的评价。
    """
    store = get_feedback_store()
    return await collect_feedback(payload, store)


@router.get("/feedback/stats", summary="查看反馈统计（内部监控用）")
async def get_feedback_stats():
    return get_feedback_store().get_stats()


@router.delete("/memory/{session_id}", summary="清除指定会话记忆")
async def clear_session(session_id: str):
    get_session_store().clear(session_id)
    return {"status": "ok", "message": f"会话 {session_id} 已清除"}


@router.get("/memory/stats", summary="查看记忆存储状态")
async def memory_stats():
    return get_session_store().stats()
