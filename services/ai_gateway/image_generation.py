from __future__ import annotations

import base64
import os
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx

try:
    from litellm import aimage_generation
except ImportError:  # pragma: no cover - exercised only outside the project env
    aimage_generation = None

from services.ai_gateway.artifacts import create_image_artifact, decode_image_data
from services.ai_gateway.config import get_ai_settings, get_ai_image_model


ImageGenerationCallable = Callable[..., Awaitable[Any]]


async def generate_ai_image(
    *,
    prompt: str,
    filename: str,
    size: str = "1024x1024",
    quality: str = "standard",
    image_generation_func: ImageGenerationCallable | None = None,
) -> dict[str, Any]:
    model = get_ai_image_model()
    if not model:
        raise ValueError(
            "AI image generation is not configured. Set AI_IMAGE_MODEL to a "
            "LiteLLM-compatible image model, for example openai/gpt-image-1."
        )
    generation = image_generation_func or aimage_generation
    if generation is None:
        raise RuntimeError("LiteLLM is required to generate AI images.")

    settings = get_ai_settings(model)
    kwargs: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if quality != "standard":
        kwargs["quality"] = quality
    if settings.api_key:
        kwargs["api_key"] = settings.api_key
    if settings.api_base:
        kwargs["api_base"] = settings.api_base

    response = await generation(**kwargs)
    item = _first_image_item(response)
    revised_prompt = _field(item, "revised_prompt") or prompt
    b64_json = _field(item, "b64_json")
    image_url = _field(item, "url")

    if b64_json:
        try:
            data = base64.b64decode(str(b64_json), validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise RuntimeError("The image provider returned invalid base64 data") from exc
        mime_type = _detect_image_mime(data)
    elif image_url and str(image_url).startswith("data:image/"):
        data, mime_type = decode_image_data(str(image_url))
    elif image_url:
        data, mime_type = await _download_generated_image(str(image_url))
    else:
        raise RuntimeError("The image provider returned no image data")

    return create_image_artifact(
        filename=filename,
        data=data,
        mime_type=mime_type,
        prompt=str(revised_prompt),
    )


def _first_image_item(response: Any) -> Any:
    data = _field(response, "data")
    if not isinstance(data, (list, tuple)) or not data:
        raise RuntimeError("The image provider returned an empty response")
    return data[0]


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


async def _download_generated_image(url: str) -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("The image provider returned an unsupported image URL")
    timeout = float(os.getenv("AI_IMAGE_DOWNLOAD_TIMEOUT", "30"))
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise RuntimeError("The generated image exceeds the 20 MB limit")
                chunks.append(chunk)
            data = b"".join(chunks)
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    mime_type = content_type if content_type.startswith("image/") else _detect_image_mime(data)
    return data, mime_type


def _detect_image_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    raise RuntimeError("The image provider returned an unsupported image format")
