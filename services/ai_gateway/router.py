import logging
from .agent_session import session_execution_lock, clear_session
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from services.annotation_service.database import get_db as get_vector_db
from services.data_service.database import get_db

from .agent_handler import (
    AgentRequestPayload,
    handle_agent,
    restore_session_messages,
)
from .artifacts import ArtifactNotFoundError, get_artifact
from .conversation_archive import (
    ConversationDetailsRequest,
    update_conversation_details,
    ConversationPinRequest,
    ConversationBranchRequest,
    ConversationImportRequest,
    pin_conversation,
    branch_conversation,
    import_conversation,
    export_conversation,
    ConversationArchiveRequest,
    ConversationRestoreRequest,
    archive_conversation,
    delete_conversation_archive,
    get_conversation_archive,
    list_conversation_archives,
)
from .config import get_ai_model
from .function_registry import (
    AIFunctionInvokeRequest,
    invoke_registered_function,
    list_registered_functions,
)
from .schema_validator import AIRequestPayload
from .translator import process_ai_task

logger = logging.getLogger("ai_gateway.router")

router = APIRouter(
    prefix="/ai",
    tags=["AI Gateway - Intelligent Spatial Data Gateway"],
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
        return await handle_agent(payload, db, vector_db, get_ai_model())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("[router] /agent failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI agent execution failed",
        )


@router.get("/artifacts/{artifact_id}/download", summary="Download an AI-generated artifact")
async def download_ai_artifact(artifact_id: str):
    try:
        metadata, path = get_artifact(artifact_id)
    except ArtifactNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI artifact not found")
    return FileResponse(
        path,
        media_type=metadata["mime_type"],
        filename=metadata["name"],
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/artifacts/{artifact_id}", summary="Preview an AI-generated artifact")
async def preview_ai_artifact(artifact_id: str):
    try:
        metadata, path = get_artifact(artifact_id)
    except ArtifactNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI artifact not found")
    is_image = str(metadata["mime_type"]).startswith("image/")
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
    }
    return FileResponse(
        path,
        media_type=metadata["mime_type"],
        filename=metadata["name"],
        content_disposition_type="inline" if is_image else "attachment",
        headers=headers,
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


@router.delete("/conversations", summary="Clear all archived AI agent conversations")
async def clear_ai_conversations():
    archives = list_conversation_archives()
    deleted = 0
    for archive in archives:
        try:
            await delete_ai_conversation(archive["archive_id"])
            deleted += 1
        except HTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise
    return {"status": "success", "deleted": deleted}


@router.get("/conversations/{archive_id}", summary="Get an archived AI agent conversation")
async def get_ai_conversation(archive_id: str):
    try:
        return {"status": "success", "conversation": get_conversation_archive(archive_id)}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation archive not found")


@router.post("/conversations/import", summary="Import a conversation as a new chat")
async def import_ai_conversation(payload: ConversationImportRequest):
    try:
        return {"status": "success", "conversation": import_conversation(payload)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/conversations/{archive_id}/export", summary="Export a portable conversation JSON")
async def export_ai_conversation(archive_id: str):
    try:
        return export_conversation(archive_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation archive not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation cannot be exported in the supported format or exceeds 20 MB")


@router.patch("/conversations/{archive_id}/pin", summary="Pin or unpin an archived conversation")
async def pin_ai_conversation(archive_id: str, payload: ConversationPinRequest):
    try:
        return {"status": "success", "conversation": pin_conversation(archive_id, payload.pinned)}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation archive not found")


@router.post("/conversations/{archive_id}/branch", summary="Branch a conversation into an independent chat")
async def branch_ai_conversation(archive_id: str, payload: ConversationBranchRequest):
    try:
        return {"status": "success", "conversation": branch_conversation(archive_id, payload)}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation archive not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/conversations/{archive_id}", summary="Edit a conversation title and note")
async def update_ai_conversation(archive_id: str, payload: ConversationDetailsRequest):
    try:
        return {"status": "success", "conversation": update_conversation_details(archive_id, payload)}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation archive not found")
    except Exception:
        logger.exception("[router] update conversation details failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Conversation update failed")


@router.delete("/conversations/{archive_id}", summary="Delete an archived AI agent conversation")
async def delete_ai_conversation(archive_id: str):
    try:
        archive = get_conversation_archive(archive_id)
        session_id = archive.get("session_id") or archive_id
        async with session_execution_lock(session_id):
            result = delete_conversation_archive(archive_id)
            clear_session(session_id)
            return result
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
    async with session_execution_lock(session_id):
        restored_count = restore_session_messages(session_id, archive.get("messages", []),
            preserve_existing=session_id == archive.get("session_id"))
    return {
        "status": "success",
        "archive_id": archive_id,
        "session_id": session_id,
        "restored_messages": restored_count,
    }
