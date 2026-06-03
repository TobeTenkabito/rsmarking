import logging
import os
import uuid
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_gateway.context_builder import build_map_context
from services.ai_gateway.config import get_ai_model
from services.ai_gateway.llm_client import acompletion, call_chat_completion
from services.ai_gateway.agent_messages import (
    assistant_message as _assistant_message,
    compact_json as _compact_json,
    json_dumps as _json_dumps,
    message_content as _message_content,
    message_tool_calls as _message_tool_calls,
    normalize_tool_call as _normalize_tool_call,
    parse_tool_arguments as _parse_tool_arguments,
)
from services.ai_gateway.agent_session import (
    MAX_SESSION_MESSAGES,
    append_session_turn as _append_session_turn,
    clear_session as _clear_session,
    get_session_history as _get_session_history,
    get_session_messages,
    restore_session_messages,
    session_execution_lock,
)
from services.ai_gateway.schema_validator import AILanguage, DataType

logger = logging.getLogger("ai_gateway.agent_handler")

class AgentRequestPayload(BaseModel):
    """Minimal tool-using agent request for the AI gateway."""

    user_prompt: str = Field(
        ...,
        min_length=2,
        max_length=4000,
        description="Natural language task for the agent.",
    )
    language: AILanguage = Field(
        default=AILanguage.EN,
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
    include_archive_memory: bool = Field(
        default=True,
        description="Include compact memory from user-saved archived conversations.",
    )
    archive_memory_limit: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum number of archived conversations to summarize for memory.",
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
    attachments: list["AgentAttachment"] = Field(
        default_factory=list,
        description="Optional files or images uploaded with the agent message.",
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


class AgentAttachment(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: Literal["image", "text", "file"] = "file"
    mime_type: str | None = Field(default=None, max_length=120)
    size: int | None = Field(default=None, ge=0)
    text_excerpt: str | None = Field(default=None, max_length=12000)
    image_data_url: str | None = Field(default=None, max_length=4_500_000)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    truncated: bool = False


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
    AILanguage.ZH: "Respond in English.",
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
    async with session_execution_lock(session_id):
        return await _handle_agent_locked(payload, db, vector_db, model_name, session_id)


async def _handle_agent_locked(
    payload: AgentRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
    model_name: str | None,
    session_id: str,
) -> dict[str, Any]:
    if payload.reset_session:
        _clear_session(session_id)

    tools = _get_agent_tools(payload.tool_names)
    allowed_tool_names = _get_allowed_tool_names(payload.tool_names)
    conversation_history = _get_session_history(session_id, payload.history_limit)
    messages = await _build_agent_messages(payload, db, vector_db, conversation_history)
    current_model = get_ai_model(model_name)
    steps: list[AgentStep] = []

    for step_number in range(1, payload.max_steps + 1):
        response = await call_chat_completion(
            model_name=current_model,
            messages=messages,
            completion_func=acompletion,
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
    response = await call_chat_completion(
        model_name=current_model,
        messages=messages,
        completion_func=acompletion,
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

    if payload.include_archive_memory and payload.archive_memory_limit > 0:
        archive_context = _build_archive_memory_context(payload.archive_memory_limit)
        if archive_context:
            messages.append({"role": "system", "content": archive_context})

    messages.extend(conversation_history)
    user_prompt = await _build_agent_user_prompt(payload, db, vector_db)
    image_parts = _build_image_content_parts(payload.attachments)
    if image_parts:
        messages.append(
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}, *image_parts],
            }
        )
    else:
        messages.append({"role": "user", "content": user_prompt})
    return messages


def _build_agent_system_prompt(language: AILanguage) -> str:
    return "\n".join(
        [
            "You are the RSMarking geospatial agent.",
            LANGUAGE_INSTRUCTIONS[language],
            "You may call only the registered AI gateway tools provided in this request.",
            "Use tools when they materially advance the task; otherwise answer directly.",
            "Tool calls can create new raster/vector outputs or run analysis jobs.",
            "Prefer dedicated geospatial tools when one fits the request.",
            "For atmospheric correction, use atmospheric_correction before generating sandbox code.",
            "For vector work, use vector project, layer, field, feature, and raster/vector conversion tools directly.",
            "If no dedicated tool can fulfill a raster-processing request, generate safe Python code and call run_script_sandbox.",
            "Before writing run_script_sandbox code, read the Sandbox Input Map from the context and use its exact sandbox_alias or open_expr values.",
            "The gateway injects stable sandbox aliases such as raster_<index_id> and raster_files[<index_id>] before the generated script runs.",
            "If you use ordered variables, map them from the raster_ids order: raster_ids[0] is input_0, raster_ids[1] is input_1, and so on.",
            "Do not invent filenames. If using the actual filename, call rasterio.open(inputs[\"actual_filename.tif\"]) exactly as shown in open_expr.",
            "For larger sandbox scripts, prefer helpers like input_path(), read_raster(), read_array(), write_raster(), sandbox_open(), output_path(), and list_inputs().",
            "Never pass the literal string 'input_file' or an unqualified guessed filename to rasterio.open().",
            "Do not claim that data was changed or created unless a tool observation confirms it.",
            "Use the workspace context to stay familiar with available projects, layers, and rasters.",
            "Use conversation archive memory only as background from user-saved prior chats.",
            "If required ids, bands, thresholds, or geometries are missing, ask a concise clarification.",
            "Final answers should summarize actions taken, important output ids or names, and any remaining caveats.",
        ]
    )


def _build_archive_memory_context(limit: int) -> str:
    try:
        from services.ai_gateway.conversation_archive import build_archive_memory_context

        return build_archive_memory_context(limit)
    except Exception as exc:
        logger.warning("[agent] conversation archive memory unavailable: %s", exc)
        return ""


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

    sandbox_context = await _build_target_sandbox_context(payload, db)
    if sandbox_context:
        sections.append(sandbox_context)

    attachment_context = _build_attachment_context(payload.attachments)
    if attachment_context:
        sections.append(attachment_context)

    sections.append(f"[User Task]\n{payload.user_prompt}")
    return "\n\n".join(sections)


def _build_attachment_context(attachments: list[AgentAttachment]) -> str:
    if not attachments:
        return ""

    lines = ["[Uploaded Attachments]"]
    for index, attachment in enumerate(attachments, start=1):
        parts = [
            f"{index}. name={attachment.name}",
            f"kind={attachment.kind}",
        ]
        if attachment.mime_type:
            parts.append(f"mime_type={attachment.mime_type}")
        if attachment.size is not None:
            parts.append(f"size_bytes={attachment.size}")
        if attachment.width and attachment.height:
            parts.append(f"dimensions={attachment.width}x{attachment.height}")
        if attachment.truncated:
            parts.append("content_truncated=true")
        lines.append(", ".join(parts))
        if attachment.text_excerpt:
            lines.append(f"excerpt:\n{attachment.text_excerpt}")
        elif attachment.kind == "image" and attachment.image_data_url:
            lines.append("image_data=attached as an OpenAI-compatible image_url part")

    return "\n".join(lines)


def _build_image_content_parts(attachments: list[AgentAttachment]) -> list[dict[str, Any]]:
    parts = []
    for attachment in attachments:
        if attachment.kind != "image" or not attachment.image_data_url:
            continue
        parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": attachment.image_data_url,
                    "detail": "auto",
                },
            }
        )
    return parts


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


async def _build_target_sandbox_context(
    payload: AgentRequestPayload,
    db: AsyncSession,
) -> str:
    if payload.target_id is None or payload.data_type != DataType.RASTER:
        return ""

    try:
        from services.data_service.crud.raster_crud import RasterCRUD

        raster = await RasterCRUD.get_raster_by_index_id(db, int(payload.target_id))
    except Exception as exc:
        logger.warning("[agent] target sandbox input map unavailable: %s", exc)
        return ""

    if not raster:
        return ""

    return "\n".join(
        [
            "[Sandbox Input Map]",
            "Use this exact mapping when generating run_script_sandbox code for the target raster.",
            "The gateway injects stable aliases before the generated script runs.",
            _format_sandbox_input_map_line(raster, ordered_variable="input_0 when this raster_id is first in raster_ids"),
        ]
    )


async def _build_workspace_context(
    db: AsyncSession,
    vector_db: AsyncSession,
    limit: int,
) -> str:
    sections = ["[Workspace Context]"]
    sections.append(
        "Compact inventory of the current RSMarking workspace. Treat ids as the "
        "source of truth and ask before destructive or ambiguous actions. For sandbox "
        "scripts, use the exact sandbox_alias or open_expr shown here; do not invent filenames."
    )

    raster_lines = await _build_raster_inventory(db, limit)
    if raster_lines:
        sections.append("Raster datasets and sandbox input map:\n" + "\n".join(raster_lines))

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
        parts.extend(_sandbox_input_map_parts(raster))
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


def _format_sandbox_input_map_line(raster: Any, ordered_variable: str | None = None) -> str:
    parts = [
        f"index_id={getattr(raster, 'index_id', '')}",
        f"name={getattr(raster, 'file_name', '')}",
        *_sandbox_input_map_parts(raster),
    ]
    if ordered_variable:
        parts.append(f"ordered_variable={ordered_variable}")
    return "- " + ", ".join(parts)


def _sandbox_input_map_parts(raster: Any) -> list[str]:
    raster_id = getattr(raster, "index_id", "")
    sandbox_filename = _sandbox_filename_for_raster(raster)
    if not sandbox_filename:
        return []

    try:
        from services.data_service.bridges.executor_bridge import _sandbox_raster_alias

        alias = _sandbox_raster_alias(raster_id)
    except Exception:
        alias = f"raster_{str(raster_id).replace('-', '_')}"

    filename_literal = _json_dumps(sandbox_filename)
    return [
        f"sandbox_alias={alias}",
        f"sandbox_filename={sandbox_filename}",
        f"open_expr=inputs[{filename_literal}]",
    ]


def _sandbox_filename_for_raster(raster: Any) -> str:
    candidates: list[Any] = []
    try:
        from services.data_service.bridges.executor_bridge import _resolve_executor_input_path

        candidates.append(_resolve_executor_input_path(raster))
    except Exception as exc:
        logger.debug("[agent] could not resolve exact sandbox path for raster: %s", exc)

    candidates.extend(
        [
            getattr(raster, "file_path", None),
            getattr(raster, "cog_path", None),
            getattr(raster, "file_name", None),
        ]
    )

    for candidate in candidates:
        filename = os.path.basename(str(candidate or "").strip())
        if filename:
            return filename
    return ""


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
        error = str(exc)
        if name == "run_script_sandbox" and "input_file" in str(arguments.get("script") or ""):
            error = (
                f"{error}\nSandbox input hint: use the exact Sandbox Input Map entries, such as "
                "raster_<index_id>, raster_files[<index_id>], or inputs[\"actual_filename.tif\"]. "
                "Do not pass the literal string 'input_file'."
            )
        return {"status": "error", "name": name, "arguments": arguments, "error": error}


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
