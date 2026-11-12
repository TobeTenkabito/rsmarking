"""Local operator configuration. Secrets never appear in API responses or prompts."""

import ipaddress
import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from .config import AISettings, BASE_DIR, _get_environment_settings


SETTINGS_PATH = BASE_DIR / "storage/ai_environment.json"
_lock = RLock()
PROVIDERS = [
    {"id": "openai", "name": "OpenAI", "transport": "openai", "base_url": "https://api.openai.com/v1", "model_hint": "Enter a Chat Completions model ID"},
    {"id": "anthropic", "name": "Anthropic / Claude", "transport": "anthropic", "base_url": "https://api.anthropic.com", "model_hint": "Enter a Claude model ID"},
    {"id": "gemini", "name": "Google / Gemini", "transport": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model_hint": "Enter a Gemini model ID"},
    {"id": "deepseek", "name": "DeepSeek", "transport": "deepseek", "base_url": "https://api.deepseek.com", "model_hint": "Enter a DeepSeek model ID"},
    {"id": "dashscope", "name": "Alibaba / Qwen", "transport": "dashscope", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model_hint": "Enter a Qwen model ID"},
    {"id": "moonshot", "name": "Moonshot / Kimi", "transport": "moonshot", "base_url": "https://api.moonshot.cn/v1", "model_hint": "Enter a Kimi model ID"},
    {"id": "zhipu", "name": "Zhipu / GLM", "transport": "zhipu", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model_hint": "Enter a GLM model ID"},
    {"id": "ollama", "name": "Ollama (local)", "transport": "openai", "base_url": "http://localhost:11434/v1", "model_hint": "Enter an installed model name"},
    {"id": "compatible", "name": "OpenAI-compatible API", "transport": "openai", "base_url": "", "model_hint": "Enter the endpoint's model ID"},
]


class EnvironmentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(min_length=1, max_length=32)
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field(max_length=1000)
    api_key: SecretStr | None = None
    timeout_ms: int = Field(default=90000, ge=1000, le=600000)
    max_tokens: int = Field(default=4096, ge=128, le=131072)
    tool_reasoning_effort: str | None = None


def _loopback(host):
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host or "")
        return address.is_loopback or bool(getattr(address, "ipv4_mapped", None) and address.ipv4_mapped.is_loopback)
    except ValueError:
        return False


def require_local_operator(request: Request):
    # CORS is permissive elsewhere in this local application. Check the browser
    # Origin and Host too, so an unrelated website cannot reconfigure the gateway.
    origin = request.headers.get("origin")
    if (not request.client or not _loopback(request.client.host)
            or not _loopback(request.url.hostname)
            or (origin and not _loopback(urlsplit(origin).hostname))):
        raise HTTPException(403, "Open Agent environment settings through localhost on the gateway machine.")


def _read_saved():
    with _lock:
        if not SETTINGS_PATH.exists():
            return None
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ValueError("Saved AI environment is unreadable; restore the .env configuration from settings.") from None


def saved_ai_settings():
    saved = _read_saved()
    try:
        return _as_ai_settings(saved) if saved else None
    except (KeyError, TypeError, StopIteration, ValueError):
        raise ValueError("Saved AI environment is invalid; restore the .env configuration from settings.") from None


def _as_ai_settings(saved):
    preset = next(item for item in PROVIDERS if item["id"] == saved["provider"])
    transport = preset["transport"]
    model = saved["model"]
    if model.startswith((saved["provider"] + "/", transport + "/")):
        model = model.split("/", 1)[1]
    key = saved.get("api_key")
    if not key:
        if saved["provider"] != "ollama" or not _loopback(urlsplit(saved["base_url"]).hostname):
            raise ValueError("Saved configuration requires an API key")
        key = "ollama-local"
    return AISettings(model=f"{transport}/{model}", provider=transport,
                      api_key=key,
                      api_base=saved["base_url"], timeout=saved["timeout_ms"] / 1000,
                      max_tokens=saved["max_tokens"], tool_reasoning_effort=saved.get("tool_reasoning_effort"))


def public_environment():
    saved = _read_saved()
    if saved:
        saved_ai_settings()
        settings = {key: value for key, value in saved.items() if key != "api_key"}
        settings.update(source="ui", has_api_key=bool(saved.get("api_key")))
    else:
        try:
            env = _get_environment_settings()
            settings = {"source": "env", "provider": env.provider, "model": env.model,
                        "base_url": env.api_base or "", "has_api_key": bool(env.api_key),
                        "timeout_ms": round(env.timeout * 1000), "max_tokens": env.max_tokens,
                        "tool_reasoning_effort": env.tool_reasoning_effort}
            # Do not expose credentials embedded in a legacy environment URL.
            parsed = urlsplit(settings["base_url"])
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                settings["base_url"] = ""
        except ValueError:
            settings = {"source": "env", "provider": "openai", "model": "", "base_url": "", "has_api_key": False}
    return {"settings": settings, "providers": [{key: value for key, value in row.items() if key != "transport"} for row in PROVIDERS]}


def save_environment(payload):
    preset = next((item for item in PROVIDERS if item["id"] == payload.provider), None)
    if preset is None:
        raise ValueError("Select a supported provider preset")
    base = payload.base_url.rstrip("/") or preset["base_url"]
    parsed = urlsplit(base)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or any(character.isspace() for character in base)
            or (parsed.scheme == "http" and not _loopback(parsed.hostname))):
        raise ValueError("Use an HTTPS API base URL, or HTTP for a local endpoint; do not include credentials or query parameters")
    if base.endswith(("/chat/completions", "/responses", "/messages")):
        raise ValueError("Use the API base URL, not a completion endpoint")
    if not payload.model.strip("/") or any(character.isspace() for character in payload.model):
        raise ValueError("Enter a valid model ID")
    if payload.tool_reasoning_effort not in {None, "none", "minimal", "low", "medium", "high"}:
        raise ValueError("Invalid tool reasoning effort")
    key = payload.api_key.get_secret_value().strip() if payload.api_key else ""
    if len(key) > 8192 or any(character.isspace() for character in key):
        raise ValueError("Invalid API key format")
    with _lock:
        previous = _read_saved()
        same_endpoint = previous and previous["provider"] == payload.provider and previous["base_url"] == base
        if not key and same_endpoint:
            key = previous.get("api_key", "")
        if not key and not (payload.provider == "ollama" and _loopback(parsed.hostname)):
            raise ValueError("Enter an API key for this provider and endpoint. Environment keys are not copied automatically.")
        data = payload.model_dump(exclude={"api_key"})
        data.update(api_key=key, base_url=base)
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".ai-environment-", dir=SETTINGS_PATH.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(data, output, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, SETTINGS_PATH)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return public_environment()


router = APIRouter(prefix="/environment", dependencies=[Depends(require_local_operator)])


@router.get("")
def read_environment():
    try:
        return JSONResponse(public_environment(), headers={"Cache-Control": "no-store"})
    except ValueError as error:
        raise HTTPException(400, str(error)) from None


@router.put("")
async def update_environment(request: Request):
    # Parse here rather than echoing Pydantic's rejected input (possibly a key)
    # in FastAPI's default 422 validation response.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 16000:
            raise HTTPException(413, "Environment settings are too large")
    try:
        payload = EnvironmentSettings.model_validate_json(body)
    except ValidationError:
        raise HTTPException(422, "Invalid environment settings. Check the model, timeout and output limit.") from None
    try:
        return JSONResponse(save_environment(payload), headers={"Cache-Control": "no-store"})
    except ValueError as error:
        raise HTTPException(400, str(error)) from None


@router.delete("")
def reset_environment():
    with _lock:
        SETTINGS_PATH.unlink(missing_ok=True)
    return JSONResponse(public_environment(), headers={"Cache-Control": "no-store"})
