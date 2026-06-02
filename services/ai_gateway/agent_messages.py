from __future__ import annotations

import json
from typing import Any


def message_content(message: Any) -> str:
    if isinstance(message, dict):
        return message.get("content") or ""
    return getattr(message, "content", None) or ""


def message_tool_calls(message: Any) -> list[Any]:
    if isinstance(message, dict):
        return message.get("tool_calls") or []
    return getattr(message, "tool_calls", None) or []


def assistant_message(message: Any, tool_calls: list[Any]) -> dict[str, Any]:
    assistant = {"role": "assistant", "content": message_content(message)}
    if tool_calls:
        assistant["tool_calls"] = [normalize_tool_call(tool_call) for tool_call in tool_calls]
    return assistant


def normalize_tool_call(tool_call: Any) -> dict[str, Any]:
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


def parse_tool_arguments(raw_arguments: str) -> tuple[dict[str, Any], str | None]:
    try:
        parsed = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as exc:
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
