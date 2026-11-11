from __future__ import annotations

import json
from typing import Any


def message_content(message: Any) -> str:
    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") in {"text", "output_text"})
    return ""


def message_tool_calls(message: Any) -> list[Any]:
    if isinstance(message, dict):
        return message.get("tool_calls") or []
    return getattr(message, "tool_calls", None) or []


def completion_message(response: Any) -> Any:
    choices = response.get("choices") if isinstance(response, dict) else getattr(response, "choices", None)
    if not choices:
        raise ValueError("The model returned no completion choices.")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)
    if message is None:
        raise ValueError("The model returned no assistant message.")
    return message


def assistant_message(message: Any, tool_calls: list[Any]) -> dict[str, Any]:
    assistant = {"role": "assistant", "content": message_content(message)}
    if tool_calls:
        assistant["tool_calls"] = [normalize_tool_call(tool_call) for tool_call in tool_calls]
    for key in ("reasoning_content", "thinking_blocks", "provider_specific_fields"):
        value = message.get(key) if isinstance(message, dict) else getattr(message, key, None)
        if value is not None:
            assistant[key] = value
    return assistant


def normalize_tool_call(tool_call: Any) -> dict[str, Any]:
    if hasattr(tool_call, "model_dump"):
        tool_call = tool_call.model_dump(exclude_none=True)
    if isinstance(tool_call, dict):
        function = tool_call.get("function") or {}
        return {
            "id": str(tool_call.get("id") or ""),
            "type": tool_call.get("type") or "function",
            "function": {
                "name": str(function.get("name") or ""),
                "arguments": _arguments_json(function.get("arguments")),
            },
            **({"provider_specific_fields": tool_call["provider_specific_fields"]} if "provider_specific_fields" in tool_call else {}),
        }

    function = getattr(tool_call, "function", None)
    return {
        "id": str(getattr(tool_call, "id", "")),
        "type": getattr(tool_call, "type", "function"),
        "function": {
            "name": str(getattr(function, "name", "") or "") if function else "",
            "arguments": _arguments_json(getattr(function, "arguments", None)) if function else "{}",
        },
    }


def _arguments_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else (value or "{}")


def parse_tool_arguments(raw_arguments: Any) -> tuple[dict[str, Any], str | None]:
    if isinstance(raw_arguments, dict):
        return dict(raw_arguments), None
    if not isinstance(raw_arguments, str):
        return {}, "Tool arguments must be a JSON object or encoded JSON string."
    try:
        parsed = json.loads(raw_arguments or "{}")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return {}, f"Tool arguments must be valid JSON: {exc}"

    if not isinstance(parsed, dict):
        return {}, "Tool arguments must decode to a JSON object."

    return parsed, None


def compact_json(value: Any, max_chars: int = 6000) -> Any:
    encoded = json_dumps(value)
    if len(encoded) <= max_chars:
        return value
    return {
        "truncated": True,
        "original_chars": len(encoded),
        "preview": encoded[:max_chars],
    }


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
