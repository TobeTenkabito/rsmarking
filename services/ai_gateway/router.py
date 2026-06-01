import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.annotation_service.database import get_db as get_vector_db
from services.data_service.database import get_db

from .agent_handler import (
    AgentRequestPayload,
    handle_agent,
    restore_session_messages,
)
from .conversation_archive import (
    ConversationArchiveRequest,
    ConversationRestoreRequest,
    archive_conversation,
    delete_conversation_archive,
    get_conversation_archive,
    list_conversation_archives,
)
from .function_registry import (
    AIFunctionInvokeRequest,
    invoke_registered_function,
    list_registered_functions,
)
from .schema_validator import AIRequestPayload
from .translator import process_ai_task

MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-chat")

logger = logging.getLogger("ai_gateway.router")

router = APIRouter(
    prefix="/ai",
    tags=["AI Gateway - 智能空间数据网关"],
)


@router.post("/process", summary="Handle AI data tasks in analyze or modify mode")
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
        logger.error("[router] /process failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI processing failed",
        )


@router.get("/functions", summary="List AI-callable algorithm functions")
async def list_ai_functions(
    format: Literal["openai", "catalog"] = "openai",
):
    return list_registered_functions(format)


@router.post("/functions/invoke", summary="Invoke an AI-callable algorithm function")
async def invoke_ai_function(
    payload: AIFunctionInvokeRequest,
    db: AsyncSession = Depends(get_db),
    vector_db: AsyncSession = Depends(get_vector_db),
):
    try:
        return await invoke_registered_function(payload, db, vector_db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("[router] /functions/invoke failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI function invocation failed",
        )


@router.post("/agent", summary="Run a minimal tool-using AI agent")
async def run_ai_agent(
    payload: AgentRequestPayload,
    db: AsyncSession = Depends(get_db),
    vector_db: AsyncSession = Depends(get_vector_db),
):
    try:
        return await handle_agent(payload, db, vector_db, MODEL)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("[router] /agent failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI agent execution failed",
        )


@router.get("/conversations", summary="List archived AI agent conversations")
async def list_ai_conversations():
    return {
        "status": "success",
        "conversations": list_conversation_archives(),
    }


@router.post("/conversations", summary="Archive an AI agent conversation")
async def archive_ai_conversation(payload: ConversationArchiveRequest):
    try:
        return {"status": "success", "conversation": archive_conversation(payload)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("[router] archive conversation failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Conversation archive failed",
        )


@router.get("/conversations/{archive_id}", summary="Get an archived AI agent conversation")
async def get_ai_conversation(archive_id: str):
    try:
        return {"status": "success", "conversation": get_conversation_archive(archive_id)}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation archive not found")


@router.delete("/conversations/{archive_id}", summary="Delete an archived AI agent conversation")
async def delete_ai_conversation(archive_id: str):
    try:
        return delete_conversation_archive(archive_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation archive not found")


@router.post("/conversations/{archive_id}/restore", summary="Restore an archive into agent session memory")
async def restore_ai_conversation(
    archive_id: str,
    payload: ConversationRestoreRequest | None = None,
):
    try:
        archive = get_conversation_archive(archive_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation archive not found")

    session_id = payload.session_id if payload and payload.session_id else archive.get("session_id") or archive_id
    restored_count = restore_session_messages(session_id, archive.get("messages", []))
    return {
        "status": "success",
        "archive_id": archive_id,
        "session_id": session_id,
        "restored_messages": restored_count,
    }
