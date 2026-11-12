import asyncio
import json
import os

import httpx
import pytest
from fastapi import FastAPI

from services.ai_gateway import environment_settings as environment
from services.ai_gateway.config import ai_settings_scope, get_ai_settings
from services.ai_gateway.llm_client import build_litellm_kwargs
from services.ai_gateway.agent_security import sanitize_error_message


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("AI_", "OPENAI_", "ANTHROPIC_", "DEEPSEEK_", "GEMINI_")):
            monkeypatch.delenv(name)


def settings(**changes):
    return environment.EnvironmentSettings(**{
        "provider": "openai", "model": "test-model", "base_url": "https://api.openai.com/v1",
        "api_key": "unit-test-key-only", **changes,
    })


def test_save_masks_secrets_and_overrides_env_without_mutating_it(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    monkeypatch.setenv("AI_MODEL", "openai/env-model")
    result = environment.save_environment(settings())
    assert result["settings"]["source"] == "ui"
    assert result["settings"]["has_api_key"] is True
    assert "unit-test-key-only" not in json.dumps(result)
    assert "environment-secret" not in json.dumps(result)
    assert get_ai_settings().api_key == "unit-test-key-only"
    assert os.environ["OPENAI_API_KEY"] == "environment-secret"
    assert "unit-test-key-only" not in sanitize_error_message("failure unit-test-key-only")
    environment.reset_environment()
    assert get_ai_settings().api_key == "environment-secret"
    assert not environment.SETTINGS_PATH.exists()


@pytest.mark.parametrize("preset", environment.PROVIDERS, ids=lambda item: item["id"])
def test_provider_presets_build_explicit_transport_and_credentials(preset):
    environment.save_environment(settings(provider=preset["id"], base_url=preset["base_url"] or "https://gateway.example/v1"))
    request = build_litellm_kwargs(messages=[])
    prefix = "anthropic" if preset["id"] == "anthropic" else "deepseek" if preset["id"] == "deepseek" else "openai"
    assert request["model"] == prefix + "/test-model"
    assert request["api_key"] == "unit-test-key-only"
    assert request["api_base"] == (preset["base_url"] or "https://gateway.example/v1")


def test_unchanged_endpoint_keeps_key_but_new_endpoint_requires_new_key():
    environment.save_environment(settings())
    environment.save_environment(settings(api_key=None, model="second-model"))
    assert get_ai_settings().api_key == "unit-test-key-only"
    for changes in ({"provider": "compatible"}, {"base_url": "https://other.example/v1"}):
        with pytest.raises(ValueError, match="Enter an API key"):
            environment.save_environment(settings(api_key=None, **changes))
    assert get_ai_settings().model == "openai/second-model"


def test_local_ollama_never_falls_back_to_environment_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-send")
    environment.save_environment(settings(provider="ollama", base_url="http://localhost:11434/v1", api_key=None))
    assert build_litellm_kwargs(messages=[])["api_key"] == "ollama-local"
    with pytest.raises(ValueError, match="Enter an API key"):
        environment.save_environment(settings(provider="ollama", base_url="https://cloud.example/v1", api_key=None))


def test_request_snapshot_survives_settings_change_and_reset():
    environment.save_environment(settings())
    with ai_settings_scope():
        environment.save_environment(settings(provider="deepseek", model="next-model", base_url="https://api.deepseek.com", api_key="next-test-key"))
        assert get_ai_settings().model == "openai/test-model"
        assert build_litellm_kwargs(model_name="openai/test-model", messages=[])["api_key"] == "unit-test-key-only"
    assert get_ai_settings().model == "deepseek/next-model"
    with ai_settings_scope():
        environment.reset_environment()
        assert get_ai_settings().api_key == "next-test-key"
    assert get_ai_settings().model != "deepseek/next-model"


@pytest.mark.parametrize("url", ["file:///secret", "https://user:password@example.com/v1", "https://example.com?key=secret",
                                 "https://example.com/v1/chat/completions", "http://public.example/v1"])
def test_invalid_addresses_do_not_replace_settings(url):
    environment.save_environment(settings())
    with pytest.raises(ValueError):
        environment.save_environment(settings(base_url=url))
    assert get_ai_settings().api_base == "https://api.openai.com/v1"


def request(method, payload=None, *, origin="http://localhost:8002", client="127.0.0.1", host="localhost"):
    app = FastAPI()
    app.include_router(environment.router, prefix="/ai")

    async def run():
        transport = httpx.ASGITransport(app=app, client=(client, 1234))
        async with httpx.AsyncClient(transport=transport, base_url=f"http://{host}:8006") as connection:
            return await connection.request(method, "/ai/environment", json=payload, headers={"Origin": origin})
    return asyncio.run(run())


def test_settings_routes_save_read_reset_and_do_not_echo_rejected_keys():
    payload = {"provider": "openai", "model": "test-model", "base_url": "https://api.openai.com/v1", "api_key": "secret-to-hide"}
    response = request("PUT", payload)
    assert response.status_code == 200
    assert "secret-to-hide" not in response.text
    assert request("GET").headers["cache-control"] == "no-store"
    invalid = request("PUT", {**payload, "max_tokens": "secret-to-hide"})
    assert invalid.status_code == 422
    assert "secret-to-hide" not in invalid.text
    assert request("DELETE").json()["settings"]["source"] == "env"


@pytest.mark.parametrize("options", [
    {"origin": "https://unrelated.example"}, {"origin": "null"},
    {"client": "192.168.1.2"}, {"host": "rebind.example"},
])
def test_remote_or_cross_origin_pages_cannot_change_settings(options):
    assert request("PUT", {}, **options).status_code == 403
    assert not environment.SETTINGS_PATH.exists()


def test_settings_route_is_registered_in_the_gateway_at_the_public_path():
    from services.ai_gateway.main import app

    async def run():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 1234))
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8006") as connection:
            response = await connection.get("/ai/environment", headers={"Origin": "http://localhost:8002"})
            assert response.status_code == 200
            assert response.json()["settings"]["source"] == "env"
    asyncio.run(run())


def test_corrupt_saved_configuration_can_be_reset_without_exposing_its_contents():
    environment.SETTINGS_PATH.write_text('{"api_key":"do-not-display"}', encoding="utf-8")
    response = request("GET")
    assert response.status_code == 400
    assert "do-not-display" not in response.text
    assert request("DELETE").status_code == 200
