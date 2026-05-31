import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.annotation_service.database import get_db as get_vector_db
from services.data_service.database import get_db

from .agent_handler import AgentRequestPayload, handle_agent
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
