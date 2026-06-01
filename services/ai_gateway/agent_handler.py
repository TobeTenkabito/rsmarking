import json
import logging
import os
import time
import uuid
from collections import deque
from threading import Lock
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from litellm import acompletion
except ImportError:  # pragma: no cover - exercised only outside the project env
    acompletion = None

from services.ai_gateway.context_builder import build_map_context
from services.ai_gateway.schema_validator import AILanguage, DataType

logger = logging.getLogger("ai_gateway.agent_handler")

SESSION_TTL_SECONDS = 6 * 60 * 60
MAX_SESSION_MESSAGES = 20
_SESSION_LOCK = Lock()
_AGENT_SESSIONS: dict[str, dict[str, Any]] = {}


class AgentRequestPayload(BaseModel):
    """Minimal tool-using agent request for the AI gateway."""

    user_prompt: str = Field(
        ...,
        min_length=2,
        max_length=4000,
        description="Natural language task for the agent.",
    )
    language: AILanguage = Field(
        default=AILanguage.ZH,
        description="Preferred response language.",
    )
    target_id: Optional[Union[int, str]] = Field(
        default=None,
        description="Optional raster index_id or vector layer UUID for context.",
    )
    data_type: Optional[DataType] = Field(
        default=None,
        description="Data type for target_id when target context is supplied.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Client-maintained session identifier.",
    )
    map_context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional map viewport, selected feature, and active-layer context.",
    )
    reset_session: bool = Field(
        default=False,
        description="Clear stored conversation state for this session before running.",
    )
    history_limit: int = Field(
        default=8,
        ge=0,
        le=20,
        description="Maximum stored conversation messages to include.",
    )
    include_workspace_context: bool = Field(
        default=True,
        description="Include a compact overview of current rasters, projects, and layers.",
    )
    workspace_limit: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum number of rasters/projects to summarize for the agent.",
    )
    max_steps: int = Field(
        default=4,
        ge=1,
        le=8,
        description="Maximum number of model tool-call turns before forcing a final answer.",
    )
    tool_names: Optional[list[str]] = Field(
        default=None,
        description="Optional allow-list of registered gateway tools the agent may call.",
    )

    @field_validator("tool_names")
    @classmethod
    def normalize_tool_names(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        cleaned = [name.strip() for name in value if name and name.strip()]
        return cleaned or None

    @model_validator(mode="after")
    def validate_target_pair(self) -> "AgentRequestPayload":
        has_target = self.target_id is not None
        has_type = self.data_type is not None
        if has_target != has_type:
            raise ValueError("target_id and data_type must be provided together")
        return self


class AgentStep(BaseModel):
    step: int
    type: Literal["tool"]
    tool_call_id: str
    name: str
    arguments: dict[str, Any]
    status: Literal["success", "error"]
    result: Any | None = None
    error: str | None = None


LANGUAGE_INSTRUCTIONS = {
    AILanguage.ZH: "Respond in Simplified Chinese.",
    AILanguage.EN: "Respond in English.",
    AILanguage.JA: "Respond in Japanese.",
}


async def handle_agent(
    payload: AgentRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
    model_name: str | None = None,
) -> dict[str, Any]:
    session_id = payload.session_id or f"agent-{uuid.uuid4()}"
    if payload.reset_session:
        _clear_session(session_id)

    tools = _get_agent_tools(payload.tool_names)
    allowed_tool_names = _get_allowed_tool_names(payload.tool_names)
    conversation_history = _get_session_history(session_id, payload.history_limit)
    messages = await _build_agent_messages(payload, db, vector_db, conversation_history)
    current_model = os.getenv("AI_NAME", model_name or os.getenv("AI_MODEL", "deepseek/deepseek-chat"))
    steps: list[AgentStep] = []
    if acompletion is None:
        raise RuntimeError("LiteLLM is required to run the AI agent.")

    for step_number in range(1, payload.max_steps + 1):
        response = await acompletion(
            model=current_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
        response_message = response.choices[0].message
        tool_calls = _message_tool_calls(response_message)
        messages.append(_assistant_message(response_message, tool_calls))

        if not tool_calls:
            return _finalize_agent_response(
                payload=payload,
                session_id=session_id,
                status="success",
                answer=_message_content(response_message),
                steps=steps,
            )

        for tool_call in tool_calls:
            normalized_call = _normalize_tool_call(tool_call)
            tool_name = normalized_call["function"]["name"]
            tool_call_id = normalized_call["id"]
            arguments, parse_error = _parse_tool_arguments(
                normalized_call["function"].get("arguments", "{}")
            )

            if parse_error:
                observation = {"status": "error", "error": parse_error}
                steps.append(
                    AgentStep(
                        step=step_number,
                        type="tool",
                        tool_call_id=tool_call_id,
                        name=tool_name,
                        arguments={},
                        status="error",
                        error=parse_error,
                    )
                )
            elif tool_name not in allowed_tool_names:
                observation = {
                    "status": "error",
                    "error": f"Tool '{tool_name}' is not available to this agent request.",
                }
                steps.append(
                    AgentStep(
                        step=step_number,
                        type="tool",
                        tool_call_id=tool_call_id,
                        name=tool_name,
                        arguments=arguments,
                        status="error",
                        error=observation["error"],
                    )
                )
            else:
                observation = await _invoke_agent_tool(tool_name, arguments, db, vector_db)
                status = "success" if observation.get("status") != "error" else "error"
                steps.append(
                    AgentStep(
                        step=step_number,
                        type="tool",
                        tool_call_id=tool_call_id,
                        name=tool_name,
                        arguments=arguments,
                        status=status,
                        result=_compact_json(observation) if status == "success" else None,
                        error=observation.get("error") if status == "error" else None,
                    )
                )

            messages.append(
                {
                    "tool_call_id": tool_call_id,
                    "role": "tool",
                    "name": tool_name,
                    "content": _json_dumps(_compact_json(observation, max_chars=12000)),
                }
            )

    messages.append(
        {
            "role": "user",
            "content": (
                "The agent step limit has been reached. Stop calling tools and provide "
                "the best final answer from the observations already available."
            ),
        }
    )
    response = await acompletion(
        model=current_model,
        messages=messages,
        temperature=0.2,
    )
    final_message = response.choices[0].message
    return _finalize_agent_response(
        payload=payload,
        session_id=session_id,
        status="max_steps_reached",
        answer=_message_content(final_message),
        steps=steps,
    )


async def _build_agent_messages(
    payload: AgentRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
    conversation_history: list[dict[str, str]],
) -> list[dict[str, Any]]:
    messages = [{"role": "system", "content": _build_agent_system_prompt(payload.language)}]

    if payload.include_workspace_context:
        workspace_context = await _build_workspace_context(db, vector_db, payload.workspace_limit)
        if workspace_context:
            messages.append({"role": "system", "content": workspace_context})

    messages.extend(conversation_history)
    messages.append({"role": "user", "content": await _build_agent_user_prompt(payload, db, vector_db)})
    return messages


def _build_agent_system_prompt(language: AILanguage) -> str:
    return "\n".join(
        [
            "You are the RSMarking geospatial agent.",
            LANGUAGE_INSTRUCTIONS[language],
            "You may call only the registered AI gateway tools provided in this request.",
            "Use tools when they materially advance the task; otherwise answer directly.",
            "Tool calls can create new raster/vector outputs or run analysis jobs.",
            "Do not claim that data was changed or created unless a tool observation confirms it.",
            "Use the workspace context to stay familiar with available projects, layers, and rasters.",
            "If required ids, bands, thresholds, or geometries are missing, ask a concise clarification.",
            "Final answers should summarize actions taken, important output ids or names, and any remaining caveats.",
        ]
    )


async def _build_agent_user_prompt(
    payload: AgentRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> str:
    sections = []
    map_context = build_map_context(payload.map_context)
    if map_context:
        sections.append(f"[Map Context]\n{map_context}")

    target_context = await _build_target_context(payload, db, vector_db)
    if target_context:
        sections.append(target_context)

    sections.append(f"[User Task]\n{payload.user_prompt}")
    return "\n\n".join(sections)


async def _build_target_context(
    payload: AgentRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> str:
    if payload.target_id is None or payload.data_type is None:
        return ""

    from services.ai_gateway.data_extractor import _extract_raster_data, _extract_vector_data

    if payload.data_type == DataType.RASTER:
        context_data = await _extract_raster_data(db, int(payload.target_id))
    else:
        context_data = await _extract_vector_data(vector_db, str(payload.target_id))

    return (
        f"[Target Context]\n"
        f"target_id={payload.target_id}\n"
        f"data_type={payload.data_type.value}\n"
        f"{context_data.model_dump_json(indent=2)}"
    )


async def _build_workspace_context(
    db: AsyncSession,
    vector_db: AsyncSession,
    limit: int,
) -> str:
    sections = ["[Workspace Context]"]
    sections.append(
        "Compact inventory of the current RSMarking workspace. Treat ids as the "
        "source of truth and ask before destructive or ambiguous actions."
    )

    raster_lines = await _build_raster_inventory(db, limit)
    if raster_lines:
        sections.append("Raster datasets:\n" + "\n".join(raster_lines))

    project_lines = await _build_vector_project_inventory(vector_db, limit)
    if project_lines:
        sections.append("Vector projects and layers:\n" + "\n".join(project_lines))

    return "\n\n".join(sections)


async def _build_raster_inventory(db: AsyncSession, limit: int) -> list[str]:
    try:
        from services.data_service.models import RasterMetadata

        stmt = (
            select(RasterMetadata)
            .order_by(RasterMetadata.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rasters = list(result.scalars().all())
    except Exception as exc:
        logger.warning("[agent] raster workspace context unavailable: %s", exc)
        return ["- unavailable"]

    if not rasters:
        return ["- none"]

    lines = []
    for raster in rasters:
        size = _format_size(getattr(raster, "width", None), getattr(raster, "height", None))
        parts = [
            f"index_id={getattr(raster, 'index_id', '')}",
            f"name={getattr(raster, 'file_name', '')}",
            f"bands={getattr(raster, 'bands', None) or 'unknown'}",
            f"crs={getattr(raster, 'crs', None) or 'unknown'}",
        ]
        if size:
            parts.append(f"size={size}")
        bundle_id = getattr(raster, "bundle_id", None)
        if bundle_id:
            parts.append(f"bundle_id={bundle_id}")
        lines.append("- " + ", ".join(parts))

    if len(rasters) == limit:
        lines.append(f"- showing newest {limit} raster records")
    return lines


async def _build_vector_project_inventory(vector_db: AsyncSession, limit: int) -> list[str]:
    try:
        from services.annotation_service.models.feature import Feature, Layer, Project

        project_stmt = (
            select(Project.id, Project.name, func.count(Layer.id).label("layer_count"))
            .outerjoin(Layer, Layer.project_id == Project.id)
            .group_by(Project.id, Project.name, Project.created_at)
            .order_by(Project.created_at.desc())
            .limit(limit)
        )
        project_result = await vector_db.execute(project_stmt)
        projects = project_result.all()
    except Exception as exc:
        logger.warning("[agent] vector workspace context unavailable: %s", exc)
        return ["- unavailable"]

    if not projects:
        return ["- none"]

    project_ids = [row.id for row in projects]
    layer_rows_by_project: dict[str, list[Any]] = {str(project_id): [] for project_id in project_ids}

    try:
        from services.annotation_service.models.feature import Feature, Layer

        layer_stmt = (
            select(
                Layer.id,
                Layer.project_id,
                Layer.name,
                Layer.source_raster_index_id,
                func.count(Feature.id).label("feature_count"),
            )
            .outerjoin(Feature, Feature.layer_id == Layer.id)
            .where(Layer.project_id.in_(project_ids))
            .group_by(Layer.id, Layer.project_id, Layer.name, Layer.source_raster_index_id)
            .order_by(Layer.name)
        )
        layer_result = await vector_db.execute(layer_stmt)
        for layer_row in layer_result.all():
            layer_rows_by_project.setdefault(str(layer_row.project_id), []).append(layer_row)
    except Exception as exc:
        logger.warning("[agent] vector layer workspace context unavailable: %s", exc)

    lines = []
    for project in projects:
        project_id = str(project.id)
        lines.append(
            f"- project_id={project_id}, name={project.name}, layers={project.layer_count}"
        )
        for layer in layer_rows_by_project.get(project_id, [])[:10]:
            source = (
                f", source_raster_index_id={layer.source_raster_index_id}"
                if layer.source_raster_index_id is not None
                else ""
            )
            lines.append(
                f"  - layer_id={layer.id}, name={layer.name}, "
                f"features={layer.feature_count}{source}"
            )

    if len(projects) == limit:
        lines.append(f"- showing newest {limit} vector projects")
    return lines


def _format_size(width: Any, height: Any) -> str:
    if width is None or height is None:
        return ""
    return f"{width}x{height}"


async def _invoke_agent_tool(
    name: str,
    arguments: dict[str, Any],
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    from services.ai_gateway.function_registry import (
        AIFunctionInvokeRequest,
        invoke_registered_function,
    )

    try:
        return await invoke_registered_function(
            AIFunctionInvokeRequest(name=name, arguments=arguments),
            db,
            vector_db,
        )
    except Exception as exc:
        logger.warning("[agent] tool invocation failed: %s", exc, exc_info=True)
        return {"status": "error", "name": name, "arguments": arguments, "error": str(exc)}


def _get_agent_tools(tool_names: list[str] | None) -> list[dict[str, Any]]:
    from services.ai_gateway.function_registry import get_registered_openai_tools

    return get_registered_openai_tools(tool_names)


def _get_allowed_tool_names(tool_names: list[str] | None) -> set[str]:
    from services.ai_gateway.function_registry import select_registered_functions

    return {function.name for function in select_registered_functions(tool_names)}


def _finalize_agent_response(
    *,
    payload: AgentRequestPayload,
    session_id: str,
    status: Literal["success", "max_steps_reached"],
    answer: str,
    steps: list[AgentStep],
) -> dict[str, Any]:
    _append_session_turn(session_id, payload.user_prompt, answer or "")
    return _agent_response(
        payload=payload,
        session_id=session_id,
        status=status,
        answer=answer,
        steps=steps,
    )


def _agent_response(
    *,
    payload: AgentRequestPayload,
    session_id: str,
    status: Literal["success", "max_steps_reached"],
    answer: str,
    steps: list[AgentStep],
) -> dict[str, Any]:
    used_tools = []
    for step in steps:
        if step.name not in used_tools:
            used_tools.append(step.name)

    return {
        "status": status,
        "mode": "agent",
        "session_id": session_id,
        "history_length": len(_get_session_history(session_id, MAX_SESSION_MESSAGES)),
        "answer": answer or "",
        "steps": [step.model_dump(exclude_none=True) for step in steps],
        "used_tools": used_tools,
    }


def _get_session_history(session_id: str, limit: int) -> list[dict[str, str]]:
    if not session_id or limit <= 0:
        return []

    _purge_expired_sessions()
    with _SESSION_LOCK:
        session = _AGENT_SESSIONS.get(session_id)
        if not session:
            return []
        messages = list(session["messages"])[-limit:]
        session["updated_at"] = time.time()
        return [dict(message) for message in messages]


def _append_session_turn(session_id: str, user_prompt: str, answer: str) -> None:
    if not session_id:
        return

    _purge_expired_sessions()
    with _SESSION_LOCK:
        session = _AGENT_SESSIONS.setdefault(
            session_id,
            {"messages": deque(maxlen=MAX_SESSION_MESSAGES), "updated_at": time.time()},
        )
        session["messages"].append({"role": "user", "content": user_prompt})
        session["messages"].append({"role": "assistant", "content": answer})
        session["updated_at"] = time.time()


def _clear_session(session_id: str) -> None:
    with _SESSION_LOCK:
        _AGENT_SESSIONS.pop(session_id, None)


def _purge_expired_sessions() -> None:
    now = time.time()
    with _SESSION_LOCK:
        expired = [
            session_id
            for session_id, session in _AGENT_SESSIONS.items()
            if now - session.get("updated_at", now) > SESSION_TTL_SECONDS
        ]
        for session_id in expired:
            _AGENT_SESSIONS.pop(session_id, None)


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        return message.get("content") or ""
    return getattr(message, "content", None) or ""


def _message_tool_calls(message: Any) -> list[Any]:
    if isinstance(message, dict):
        return message.get("tool_calls") or []
    return getattr(message, "tool_calls", None) or []


def _assistant_message(message: Any, tool_calls: list[Any]) -> dict[str, Any]:
    assistant = {"role": "assistant", "content": _message_content(message)}
    if tool_calls:
        assistant["tool_calls"] = [_normalize_tool_call(tool_call) for tool_call in tool_calls]
    return assistant


def _normalize_tool_call(tool_call: Any) -> dict[str, Any]:
    if isinstance(tool_call, dict):
        function = tool_call.get("function") or {}
        return {
            "id": str(tool_call.get("id") or ""),
            "type": tool_call.get("type") or "function",
            "function": {
                "name": function.get("name") or "",
                "arguments": function.get("arguments") or "{}",
            },
        }

    function = getattr(tool_call, "function", None)
    return {
        "id": str(getattr(tool_call, "id", "")),
        "type": getattr(tool_call, "type", "function"),
        "function": {
            "name": getattr(function, "name", "") if function else "",
            "arguments": getattr(function, "arguments", "{}") if function else "{}",
        },
    }


def _parse_tool_arguments(raw_arguments: str) -> tuple[dict[str, Any], str | None]:
    try:
        parsed = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as exc:
        return {}, f"Tool arguments must be valid JSON: {exc}"

    if not isinstance(parsed, dict):
        return {}, "Tool arguments must decode to a JSON object."

    return parsed, None


def _compact_json(value: Any, max_chars: int = 6000) -> Any:
    encoded = _json_dumps(value)
    if len(encoded) <= max_chars:
        return value
    return {
        "truncated": True,
        "original_chars": len(encoded),
        "preview": encoded[:max_chars],
    }


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
