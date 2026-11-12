from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
    api_key: str | None = field(default=None, repr=False)
    api_base: str | None = None
    timeout: float = 30.0
    max_tokens: int = 4096
    api_version: str | None = None
    reasoning_enabled: bool = False
    reasoning_effort: str | None = None
    tool_reasoning_effort: str | None = None
    reasoning_budget_tokens: int | None = None
    reasoning_style: str = "auto"
    reasoning_model_allowlist: tuple[str, ...] = field(default_factory=tuple)
    reasoning_extra: dict[str, Any] = field(default_factory=dict)


    @property
    def litellm_model(self) -> str:
        if self.provider in _COMPATIBLE_BASES:
            return "openai/" + self.model.split("/", 1)[-1]
        return self.model


_ALIASES = {"google": "gemini", "qwen": "dashscope", "doubao": "ark", "volcengine": "ark", "baidu": "qianfan", "compatible": "openai", "ollama": "ollama_chat"}
_PREFIXES = {"gemini": ("GEMINI", "GOOGLE"), "dashscope": ("DASHSCOPE", "QWEN"), "ark": ("ARK", "DOUBAO"), "ollama_chat": ("OLLAMA",)}
_COMPATIBLE_BASES = {
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ark": "https://ark.cn-beijing.volces.com/api/v3",
    "qianfan": "https://qianfan.baidubce.com/v2",
    "moonshot": "https://api.moonshot.cn/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}
_PROVIDERS = {"openai", "anthropic", "gemini", "deepseek", "openrouter", "groq", "mistral", "xai", "azure", "ollama_chat", *_COMPATIBLE_BASES}
_EMPTY_VALUES.update({"your_api_key", "your-api-key", "your_model", "<your-api-key>", "hidden", "redacted", "***"})


_request_settings: ContextVar[AISettings | None] = ContextVar("ai_request_settings", default=None)


def get_ai_settings(model_name: str | None = None) -> AISettings:
    settings = _request_settings.get()
    if settings is None:
        from .environment_settings import saved_ai_settings

        settings = saved_ai_settings()
    if settings is not None and (model_name is None or model_name in {settings.model, settings.litellm_model}):
        return settings
    return _get_environment_settings(model_name)


@contextmanager
def ai_settings_scope():
    """One request keeps one provider/key snapshot even if settings change mid-task."""
    token = _request_settings.set(get_ai_settings())
    try:
        yield
    finally:
        _request_settings.reset(token)


def _get_environment_settings(model_name: str | None = None) -> AISettings:
    explicit = _first_env(["AI_PROVIDER"])
    explicit = _ALIASES.get(explicit.lower(), explicit.lower()) if explicit else None
    if explicit and explicit not in _PROVIDERS:
        raise ValueError("Unknown AI_PROVIDER; use a documented provider or openai for a compatible gateway.")
    model = _clean_env_value(model_name) or _first_env(["AI_MODEL", "AI_NAME", "AI_MODEL_NAME"])
    if not model:
        provider = explicit or "openai"
        model = _first_env([f"{prefix}_MODEL" for prefix in _prefixes(provider)])
        if not model:
            if provider != "openai":
                raise ValueError("Set AI_MODEL or the selected provider's *_MODEL variable.")
            model = "gpt-4o"
    prefix, separator, remainder = model.partition("/")
    canonical = _ALIASES.get(prefix.lower(), prefix.lower())
    # Provider prefixes are lowercase; e.g. Qwen/Model is an organization/model
    # identifier, not the qwen/ provider alias.
    if separator and prefix == prefix.lower() and canonical in _PROVIDERS:
        provider = canonical
        model = f"{provider}/{remainder}"
        if not remainder:
            raise ValueError("AI_MODEL must include a model name after the provider prefix.")
    else:
        provider = explicit or _infer_provider(model)
        model = f"{provider}/{model}"
    timeout_ms = _int_env("AI_TIMEOUT")
    max_tokens = _int_env("AI_MAX_TOKENS")
    timeout_ms = 30000 if timeout_ms is None else timeout_ms
    max_tokens = 4096 if max_tokens is None else max_tokens
    if timeout_ms <= 0 or max_tokens <= 0:
        raise ValueError("AI_TIMEOUT and AI_MAX_TOKENS must be positive integers.")
    return AISettings(
        model=model, provider=provider,
        api_key=_resolve_api_key(provider), api_base=_resolve_api_base(provider),
        timeout=timeout_ms / 1000, max_tokens=max_tokens,
        api_version=_first_env(["AZURE_API_VERSION"]) if provider == "azure" else None,
        reasoning_enabled=_bool_env("AI_REASONING_ENABLED", default=False),
        reasoning_effort=_clean_env_value(os.getenv("AI_REASONING_EFFORT") or "medium"),
        tool_reasoning_effort=_clean_env_value(os.getenv("AI_TOOL_REASONING_EFFORT") or "") or None,
        reasoning_budget_tokens=_int_env("AI_REASONING_BUDGET_TOKENS"),
        reasoning_style=_clean_env_value(os.getenv("AI_REASONING_STYLE") or "auto").lower(),
        reasoning_model_allowlist=_csv_env("AI_REASONING_MODEL_ALLOWLIST"),
        reasoning_extra=_json_env("AI_REASONING_EXTRA_JSON"),
    )


def get_ai_model(model_name: str | None = None) -> str:
    return get_ai_settings(model_name).model


def get_ai_image_model() -> str | None:
    """Return the separately configured image model, if image generation is enabled."""
    value = _clean_env_value(os.getenv("AI_IMAGE_MODEL") or "")
    return value or None


def build_litellm_kwargs(
    *,
    model_name: str | None = None,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Compatibility wrapper; request construction lives in llm_client."""
    from services.ai_gateway.llm_client import build_litellm_kwargs as _build_litellm_kwargs

    return _build_litellm_kwargs(model_name=model_name, messages=messages, **kwargs)


def log_ai_settings() -> None:
    settings = get_ai_settings()
    parsed = urlsplit(settings.api_base or "")
    safe_base = f"{parsed.scheme}://{parsed.hostname}{parsed.path}" if settings.api_base else "default"
    logger.info(
        "AI model configuration: model=%s provider=%s api_base=%s api_key_configured=%s reasoning_enabled=%s",
        settings.model,
        settings.provider or "unknown",
        safe_base,
        bool(settings.api_key),
        settings.reasoning_enabled,
    )
    logger.info(
        "AI image generation configuration: model=%s enabled=%s",
        get_ai_image_model() or "not configured",
        bool(get_ai_image_model()),
    )


def _infer_provider(model: str) -> str:
    lower = model.lower()
    for prefix, provider in (("claude-", "anthropic"), ("gemini-", "gemini"), ("deepseek-", "deepseek"), ("qwen", "dashscope"), ("qwq", "dashscope"), ("doubao-", "ark"), ("ernie-", "qianfan")):
        if lower.startswith(prefix):
            return provider
    return "openai"


def _prefixes(provider: str) -> tuple[str, ...]:
    return _PREFIXES.get(provider, (provider.upper(),))


def _resolve_api_key(provider: str | None) -> str | None:
    return _first_env(["AI_API_KEY"] + [f"{prefix}_API_KEY" for prefix in _prefixes(provider or "openai")])


def _resolve_api_base(provider: str | None) -> str | None:
    candidates = ["AI_BASE_URL", "AI_API_BASE"]
    for prefix in _prefixes(provider or "openai"):
        candidates.extend([f"{prefix}_BASE_URL", f"{prefix}_API_BASE"])
    value = _first_env(candidates) or _COMPATIBLE_BASES.get(provider)
    if value:
        value = value.rstrip("/")
        if value.endswith(("/chat/completions", "/responses", "/messages")):
            raise ValueError("Set an API base URL, not a /chat/completions, /responses or /messages endpoint.")
    return value


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
    # dotenv already parses comments; preserve literal hashes in keys and JSON.
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
