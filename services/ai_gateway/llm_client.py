from __future__ import annotations

from typing import Any, Awaitable, Callable

try:
    from litellm import acompletion
except ImportError:  # pragma: no cover - exercised only outside the project env
    acompletion = None

from services.ai_gateway.config import get_ai_settings
from services.ai_gateway.reasoning import build_reasoning_kwargs


CompletionCallable = Callable[..., Awaitable[Any]]


def build_litellm_kwargs(
    *,
    model_name: str | None = None,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = get_ai_settings(model_name)
    request_kwargs = {
        "model": settings.litellm_model,
        "messages": messages,
        "timeout": settings.timeout,
        "max_tokens": settings.max_tokens,
        **{key: value for key, value in kwargs.items() if value is not None},
    }
    if settings.api_key:
        request_kwargs["api_key"] = settings.api_key
    elif settings.provider in {"dashscope", "ark", "qianfan", "moonshot", "zhipu", "siliconflow"}:
        # These use LiteLLM's OpenAI transport; absent keys would otherwise fall
        # back to OPENAI_API_KEY inside LiteLLM and leak it to another service.
        raise ValueError(f"Configure {settings.provider.upper()}_API_KEY or AI_API_KEY for this provider.")
    if settings.api_base:
        request_kwargs["api_base"] = settings.api_base
    if settings.api_version:
        request_kwargs["api_version"] = settings.api_version
    if not request_kwargs.get("tools"):
        request_kwargs.pop("tools", None)
        request_kwargs.pop("tool_choice", None)

    reasoning_kwargs = build_reasoning_kwargs(settings)
    if reasoning_kwargs:
        request_kwargs.update(reasoning_kwargs)
    base_model = settings.model.split("/", 1)[-1].lower()
    if settings.provider == "openai" and base_model.startswith("gpt-6") and "reasoning_effort" in request_kwargs:
        # LiteLLM 1.82.x predates GPT-6 and otherwise rejects this documented
        # OpenAI parameter before sending the request. Keep provider validation
        # enabled for all other parameters; never silently drop reasoning/tools.
        allowed = list(request_kwargs.get("allowed_openai_params") or [])
        if "reasoning_effort" not in allowed:
            allowed.append("reasoning_effort")
        request_kwargs["allowed_openai_params"] = allowed
    if settings.provider == "openai" and base_model.startswith(("o1", "o3", "o4", "gpt-5", "gpt-6")):
        request_kwargs.pop("temperature", None)
        if "max_tokens" in request_kwargs:
            request_kwargs.setdefault("max_completion_tokens", request_kwargs.pop("max_tokens"))
    if request_kwargs.get("thinking", {}).get("type") == "enabled":
        request_kwargs.pop("temperature", None)
        if request_kwargs.get("max_tokens", 0) <= request_kwargs["thinking"].get("budget_tokens", 0):
            raise ValueError("AI_MAX_TOKENS must exceed the Anthropic thinking budget.")
    return request_kwargs


async def call_chat_completion(
    *,
    model_name: str | None = None,
    messages: list[dict[str, Any]],
    completion_func: CompletionCallable | None = None,
    **kwargs: Any,
) -> Any:
    completion = completion_func or acompletion
    if completion is None:
        raise RuntimeError("LiteLLM is required to run AI Gateway model calls.")

    return await completion(
        **build_litellm_kwargs(
            model_name=model_name,
            messages=messages,
            **kwargs,
        )
    )
