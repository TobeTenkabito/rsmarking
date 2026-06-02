from __future__ import annotations

import logging
import re
from typing import Any

from services.ai_gateway.config import AISettings


logger = logging.getLogger("ai_gateway.reasoning")

_OPENAI_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")
_ANTHROPIC_THINKING_MARKERS = ("claude-3-7", "claude-sonnet-4", "claude-opus-4")


def build_reasoning_kwargs(settings: AISettings) -> dict[str, Any]:
    """Return provider-safe reasoning parameters for a LiteLLM request."""
    if not settings.reasoning_enabled:
        return {}
    if not reasoning_supported(settings):
        logger.info(
            "AI reasoning mode requested but not enabled for model=%s provider=%s",
            settings.model,
            settings.provider or "unknown",
        )
        return {}

    style = resolve_reasoning_style(settings)
    params: dict[str, Any] = {}
    if style == "openai":
        if settings.reasoning_effort:
            params["reasoning_effort"] = settings.reasoning_effort
    elif style == "anthropic":
        budget = settings.reasoning_budget_tokens or 1024
        params["thinking"] = {"type": "enabled", "budget_tokens": budget}
    elif style in {"dashscope", "qwen"}:
        extra_body = {"enable_thinking": True}
        if settings.reasoning_budget_tokens is not None:
            extra_body["thinking_budget"] = settings.reasoning_budget_tokens
        params["extra_body"] = extra_body

    params = _deep_merge(params, settings.reasoning_extra)
    if params:
        logger.info(
            "AI reasoning mode enabled for model=%s provider=%s style=%s params=%s",
            settings.model,
            settings.provider or "unknown",
            style,
            sorted(params.keys()),
        )
    return params


def reasoning_supported(settings: AISettings) -> bool:
    model = settings.model.lower()
    base_model = model.split("/", 1)[-1]

    if settings.reasoning_model_allowlist:
        return _matches_any(model, settings.reasoning_model_allowlist) or _matches_any(
            base_model,
            settings.reasoning_model_allowlist,
        )

    provider = (settings.provider or "").lower()
    if provider == "openai":
        return base_model.startswith(_OPENAI_REASONING_PREFIXES)
    if provider == "anthropic":
        return any(marker in base_model for marker in _ANTHROPIC_THINKING_MARKERS)
    if provider == "deepseek":
        return "reasoner" in base_model or base_model.endswith("-r1")
    if provider in {"dashscope", "qwen"}:
        return "qwen3" in base_model or "qwq" in base_model
    return False


def resolve_reasoning_style(settings: AISettings) -> str:
    style = settings.reasoning_style
    if style != "auto":
        return style
    provider = (settings.provider or "").lower()
    model = settings.model.lower()
    base_model = model.split("/", 1)[-1]
    if provider == "anthropic":
        return "anthropic"
    if provider in {"dashscope", "qwen"}:
        return "dashscope"
    if provider == "deepseek":
        return "custom"
    if provider == "openai" or base_model.startswith(_OPENAI_REASONING_PREFIXES):
        return "openai"
    return "custom"


def _matches_any(value: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        regex = "^" + re.escape(pattern).replace("\\*", ".*") + "$"
        if re.match(regex, value):
            return True
    return False


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in updates.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
