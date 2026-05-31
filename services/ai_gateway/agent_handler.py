import json
import logging
import os
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from litellm import acompletion
except ImportError:  # pragma: no cover - exercised only outside the project env
    acompletion = None

from services.ai_gateway.context_builder import build_map_context
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
    tools = _get_agent_tools(payload.tool_names)
    allowed_tool_names = _get_allowed_tool_names(payload.tool_names)
    messages = await _build_agent_messages(payload, db, vector_db)
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
            return _agent_response(
                payload=payload,
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
    return _agent_response(
        payload=payload,
        status="max_steps_reached",
        answer=_message_content(final_message),
        steps=steps,
    )


async def _build_agent_messages(
    payload: AgentRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": _build_agent_system_prompt(payload.language)},
        {"role": "user", "content": await _build_agent_user_prompt(payload, db, vector_db)},
    ]


def _build_agent_system_prompt(language: AILanguage) -> str:
    return "\n".join(
        [
            "You are the RSMarking geospatial agent.",
            LANGUAGE_INSTRUCTIONS[language],
            "You may call only the registered AI gateway tools provided in this request.",
            "Use tools when they materially advance the task; otherwise answer directly.",
            "Tool calls can create new raster/vector outputs or run analysis jobs.",
            "Do not claim that data was changed or created unless a tool observation confirms it.",
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


def _agent_response(
    *,
    payload: AgentRequestPayload,
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
        "session_id": payload.session_id,
        "answer": answer or "",
        "steps": [step.model_dump(exclude_none=True) for step in steps],
        "used_tools": used_tools,
    }


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
