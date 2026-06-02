from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


logger = logging.getLogger("ai_gateway.config")

CURRENT_DIR = Path(__file__).resolve().parent
BASE_DIR = CURRENT_DIR.parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH, override=False)


_EMPTY_VALUES = {"", "your model", '"your model"', "your key", '"your key"'}
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_OPENAI_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")
_ANTHROPIC_THINKING_MARKERS = ("claude-3-7", "claude-sonnet-4", "claude-opus-4")


@dataclass(frozen=True)
class AISettings:
    model: str
    provider: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    reasoning_enabled: bool = False
    reasoning_effort: str | None = None
    reasoning_budget_tokens: int | None = None
    reasoning_style: str = "auto"
    reasoning_model_allowlist: tuple[str, ...] = field(default_factory=tuple)
    reasoning_extra: dict[str, Any] = field(default_factory=dict)


def get_ai_settings(model_name: str | None = None) -> AISettings:
    model = _clean_env_value(
        model_name
        or os.getenv("AI_MODEL")
        or os.getenv("AI_NAME")
        or os.getenv("AI_MODEL_NAME")
        or os.getenv("OPENAI_MODEL")
        or "deepseek/deepseek-chat"
    )
    provider = _provider_from_model(model)
    reasoning_extra = _json_env("AI_REASONING_EXTRA_JSON")
    return AISettings(
        model=model,
        provider=provider,
        api_key=_resolve_api_key(provider),
        api_base=_resolve_api_base(provider),
        reasoning_enabled=_bool_env("AI_REASONING_ENABLED", default=False),
        reasoning_effort=_clean_env_value(os.getenv("AI_REASONING_EFFORT") or "medium"),
        reasoning_budget_tokens=_int_env("AI_REASONING_BUDGET_TOKENS"),
        reasoning_style=_clean_env_value(os.getenv("AI_REASONING_STYLE") or "auto").lower(),
        reasoning_model_allowlist=_csv_env("AI_REASONING_MODEL_ALLOWLIST"),
        reasoning_extra=reasoning_extra,
    )


def get_ai_model(model_name: str | None = None) -> str:
    return get_ai_settings(model_name).model


def build_litellm_kwargs(
    *,
    model_name: str | None = None,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = get_ai_settings(model_name)
    request_kwargs = {
        "model": settings.model,
        "messages": messages,
        **{key: value for key, value in kwargs.items() if value is not None},
    }
    if settings.api_key:
        request_kwargs["api_key"] = settings.api_key
    if settings.api_base:
        request_kwargs["api_base"] = settings.api_base

    reasoning_kwargs = build_reasoning_kwargs(settings)
    if reasoning_kwargs:
        request_kwargs.update(reasoning_kwargs)
    return request_kwargs


def build_reasoning_kwargs(settings: AISettings) -> dict[str, Any]:
    if not settings.reasoning_enabled:
        return {}
    if not _reasoning_supported(settings):
        logger.info(
            "AI reasoning mode requested but not enabled for model=%s provider=%s",
            settings.model,
            settings.provider or "unknown",
        )
        return {}

    style = _resolve_reasoning_style(settings)
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


def log_ai_settings() -> None:
    settings = get_ai_settings()
    logger.info(
        "AI model configuration: model=%s provider=%s api_base=%s api_key_configured=%s reasoning_enabled=%s",
        settings.model,
        settings.provider or "unknown",
        settings.api_base or "default",
        bool(settings.api_key),
        settings.reasoning_enabled,
    )


def _reasoning_supported(settings: AISettings) -> bool:
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


def _resolve_reasoning_style(settings: AISettings) -> str:
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
        return "custom" if not settings.reasoning_extra else "custom"
    if provider == "openai" or base_model.startswith(_OPENAI_REASONING_PREFIXES):
        return "openai"
    return "custom"


def _provider_from_model(model: str) -> str | None:
    if "/" in model:
        return model.split("/", 1)[0].strip().lower()
    explicit = _clean_env_value(os.getenv("AI_PROVIDER") or "")
    if explicit:
        return explicit.lower()
    return "openai"


def _resolve_api_key(provider: str | None) -> str | None:
    candidates = ["AI_API_KEY"]
    if provider:
        candidates.append(f"{provider.upper()}_API_KEY")
    candidates.append("OPENAI_API_KEY")
    return _first_env(candidates)


def _resolve_api_base(provider: str | None) -> str | None:
    candidates = ["AI_BASE_URL", "AI_API_BASE"]
    if provider:
        prefix = provider.upper()
        candidates.extend([f"{prefix}_BASE_URL", f"{prefix}_API_BASE"])
    candidates.extend(["OPENAI_BASE_URL", "OPENAI_API_BASE"])
    return _first_env(candidates)


def _first_env(names: list[str]) -> str | None:
    for name in names:
        value = _clean_env_value(os.getenv(name) or "")
        if value and not _is_placeholder_value(value):
            return value
    return None


def _is_placeholder_value(value: str) -> bool:
    lowered = value.lower().strip()
    if lowered in _EMPTY_VALUES:
        return True
    if "xxxxxxxx" in lowered:
        return True
    return False


def _clean_env_value(value: str | None) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    if "#" in value:
        value = value.split("#", 1)[0].strip()
    return value.strip("\"'")


def _bool_env(name: str, *, default: bool = False) -> bool:
    value = _clean_env_value(os.getenv(name) or "")
    if not value:
        return default
    return value.lower() in _TRUE_VALUES


def _int_env(name: str) -> int | None:
    value = _clean_env_value(os.getenv(name) or "")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning("Ignoring invalid integer environment value for %s", name)
        return None


def _csv_env(name: str) -> tuple[str, ...]:
    value = _clean_env_value(os.getenv(name) or "")
    if not value:
        return ()
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


def _json_env(name: str) -> dict[str, Any]:
    value = _clean_env_value(os.getenv(name) or "")
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid JSON environment value for %s", name)
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
