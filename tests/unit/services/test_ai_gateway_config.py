from services.ai_gateway.config import build_litellm_kwargs, get_ai_settings


_ENV_KEYS = [
    "AI_MODEL",
    "AI_NAME",
    "AI_MODEL_NAME",
    "OPENAI_MODEL",
    "AI_PROVIDER",
    "AI_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
    "AI_BASE_URL",
    "AI_API_BASE",
    "OPENAI_BASE_URL",
    "DEEPSEEK_BASE_URL",
    "DASHSCOPE_BASE_URL",
    "AI_REASONING_ENABLED",
    "AI_REASONING_EFFORT",
    "AI_REASONING_STYLE",
    "AI_REASONING_MODEL_ALLOWLIST",
    "AI_REASONING_BUDGET_TOKENS",
    "AI_REASONING_EXTRA_JSON",
]


def _clear_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_reasoning_disabled_by_default(monkeypatch):
    _clear_env(monkeypatch)

    kwargs = build_litellm_kwargs(
        model_name="openai/o3-mini",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.2,
    )

    assert kwargs["model"] == "openai/o3-mini"
    assert "reasoning_effort" not in kwargs
    assert "thinking" not in kwargs
    assert "extra_body" not in kwargs


def test_openai_reasoning_effort_is_added_for_supported_model(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("AI_REASONING_ENABLED", "true")
    monkeypatch.setenv("AI_REASONING_EFFORT", "high")

    kwargs = build_litellm_kwargs(
        model_name="openai/o3-mini",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert kwargs["reasoning_effort"] == "high"


def test_reasoning_not_sent_to_standard_model(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("AI_REASONING_ENABLED", "true")
    monkeypatch.setenv("AI_REASONING_EFFORT", "high")

    kwargs = build_litellm_kwargs(
        model_name="openai/gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert "reasoning_effort" not in kwargs


def test_provider_specific_qwen_thinking_params(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("AI_REASONING_ENABLED", "1")
    monkeypatch.setenv("AI_REASONING_BUDGET_TOKENS", "2048")

    kwargs = build_litellm_kwargs(
        model_name="dashscope/qwen3-plus",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert kwargs["extra_body"] == {
        "enable_thinking": True,
        "thinking_budget": 2048,
    }


def test_model_and_provider_connection_settings_are_centralized(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("AI_MODEL", "deepseek/deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    settings = get_ai_settings()
    kwargs = build_litellm_kwargs(messages=[{"role": "user", "content": "hello"}])

    assert settings.model == "deepseek/deepseek-chat"
    assert settings.provider == "deepseek"
    assert kwargs["api_key"] == "deepseek-key"
    assert kwargs["api_base"] == "https://api.deepseek.com/v1"


def test_global_api_key_overrides_provider_placeholder(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("AI_MODEL", "deepseek/deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    monkeypatch.setenv("AI_API_KEY", "global-key")

    kwargs = build_litellm_kwargs(messages=[{"role": "user", "content": "hello"}])

    assert kwargs["api_key"] == "global-key"
