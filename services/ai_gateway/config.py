from __future__ import annotations

import json
import logging
import os
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
