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
