"""Offline, secret-safe diagnostics: python -m services.ai_gateway.diagnose."""
import json
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values


def main():
    env_path = Path(__file__).resolve().parents[2] / ".env"
    file_values = dotenv_values(env_path)
    overrides = sorted(key for key, value in file_values.items() if key.startswith(("AI_", "OPENAI_", "ANTHROPIC_", "GEMINI_", "GOOGLE_", "DEEPSEEK_", "DASHSCOPE_", "ARK_", "QIANFAN_")) and key in os.environ and os.environ[key] != value)
    from services.ai_gateway.config import get_ai_settings, _prefixes, _first_env
    from services.ai_gateway.llm_client import build_litellm_kwargs
    from services.ai_gateway.environment_settings import saved_ai_settings
    settings = get_ai_settings()
    request = build_litellm_kwargs(messages=[{"role": "user", "content": "offline diagnostic"}], temperature=0.2)
    names = ["AI_API_KEY"] + [f"{prefix}_API_KEY" for prefix in _prefixes(settings.provider)]
    key_source = next((name for name in names if _first_env([name])), None)
    configuration_source = "ui" if saved_ai_settings() is not None else "env"
    if configuration_source == "ui":
        key_source = "local gateway configuration"
    parsed = urlsplit(settings.api_base or "")
    try:
        library_version = version("litellm")
    except PackageNotFoundError:
        library_version = "not installed"
    print(json.dumps({
        "env_file": str(env_path), "env_file_exists": env_path.is_file(),
        "process_overrides": overrides, "model": settings.model,
        "provider": settings.provider, "request_model": settings.litellm_model,
        "configuration_source": configuration_source,
        "api_base": f"{parsed.scheme}://{parsed.hostname}{parsed.path}" if settings.api_base else "provider default",
        "api_key_configured": bool(settings.api_key), "api_key_source": key_source,
        "timeout_seconds": settings.timeout, "max_tokens": settings.max_tokens,
        "reasoning_enabled": settings.reasoning_enabled,
        "reasoning_effort": request.get("reasoning_effort"),
        "request_parameter_names": sorted(request), "litellm_version": library_version,
        "live_request_sent": False,
        "note": "Offline checks cannot verify credentials, model access, billing or connectivity. Restart ai_gateway after editing .env.",
    }, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
