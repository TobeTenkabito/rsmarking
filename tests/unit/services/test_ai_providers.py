import asyncio
import os
from types import SimpleNamespace

import pytest

from services.ai_gateway.config import get_ai_settings
from services.ai_gateway.llm_client import build_litellm_kwargs, call_chat_completion
from services.ai_gateway.agent_messages import assistant_message, completion_message, message_content


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    prefixes = ('AI_', 'OPENAI_', 'ANTHROPIC_', 'GEMINI_', 'GOOGLE_', 'DEEPSEEK_', 'DASHSCOPE_', 'QWEN_', 'ARK_', 'DOUBAO_', 'QIANFAN_', 'MOONSHOT_', 'ZHIPU_', 'SILICONFLOW_', 'AZURE_', 'OLLAMA_', 'OPENROUTER_')
    for key in list(os.environ):
        if key.startswith(prefixes):
            monkeypatch.delenv(key)


@pytest.mark.parametrize('model,provider,routed,key_name', [
    ('gpt-4o', 'openai', 'openai/gpt-4o', 'OPENAI_API_KEY'),
    ('claude-sonnet-4-6', 'anthropic', 'anthropic/claude-sonnet-4-6', 'ANTHROPIC_API_KEY'),
    ('google/gemini-2.5-flash', 'gemini', 'gemini/gemini-2.5-flash', 'GOOGLE_API_KEY'),
    ('deepseek-chat', 'deepseek', 'deepseek/deepseek-chat', 'DEEPSEEK_API_KEY'),
    ('qwen/qwen-plus', 'dashscope', 'openai/qwen-plus', 'DASHSCOPE_API_KEY'),
    ('doubao/ep-test', 'ark', 'openai/ep-test', 'ARK_API_KEY'),
    ('qianfan/ernie-test', 'qianfan', 'openai/ernie-test', 'QIANFAN_API_KEY'),
    ('moonshot/kimi-test', 'moonshot', 'openai/kimi-test', 'MOONSHOT_API_KEY'),
    ('zhipu/glm-test', 'zhipu', 'openai/glm-test', 'ZHIPU_API_KEY'),
    ('siliconflow/Qwen/Qwen3-8B', 'siliconflow', 'openai/Qwen/Qwen3-8B', 'SILICONFLOW_API_KEY'),
    ('openrouter/anthropic/claude-test', 'openrouter', 'openrouter/anthropic/claude-test', 'OPENROUTER_API_KEY'),
])
def test_provider_route_and_key_selection(monkeypatch, model, provider, routed, key_name):
    monkeypatch.setenv('AI_MODEL', model)
    monkeypatch.setenv(key_name, 'test-provider-key')
    assert get_ai_settings().provider == provider
    request = build_litellm_kwargs(messages=[])
    assert request['model'] == routed
    assert request['api_key'] == 'test-provider-key'


def test_provider_model_variable_and_explicit_gateway(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'anthropic')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'claude-test')
    assert get_ai_settings().model == 'anthropic/claude-test'
    monkeypatch.setenv('AI_PROVIDER', 'openai')
    monkeypatch.setenv('AI_MODEL', 'Qwen/organization-model')
    assert get_ai_settings().litellm_model == 'openai/Qwen/organization-model'


def test_other_providers_never_inherit_openai_credentials(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'private-openai-key')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://private.example/v1')
    for model in ('anthropic/claude-test', 'gemini/gemini-test', 'deepseek/deepseek-chat', 'dashscope/qwen-plus'):
        settings = get_ai_settings(model)
        assert settings.api_key is None
        assert settings.api_base != 'https://private.example/v1'
    with pytest.raises(ValueError, match='DASHSCOPE_API_KEY'):
        build_litellm_kwargs(model_name='dashscope/qwen-plus', messages=[])


def test_placeholder_model_falls_back_and_hash_in_key_is_preserved(monkeypatch):
    monkeypatch.setenv('AI_MODEL', 'your model')
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-test')
    monkeypatch.setenv('OPENAI_API_KEY', 'test#literal')
    settings = get_ai_settings()
    assert settings.model == 'openai/gpt-test'
    assert settings.api_key == 'test#literal'
    assert 'test#literal' not in repr(settings)


def test_timeout_tokens_and_reasoning_request(monkeypatch):
    monkeypatch.setenv('AI_TIMEOUT', '45000')
    monkeypatch.setenv('AI_MAX_TOKENS', '8192')
    request = build_litellm_kwargs(model_name='openai/gpt-6.1-sol', messages=[], temperature=0.2, tool_choice='auto')
    assert request['timeout'] == 45
    assert request['max_completion_tokens'] == 8192
    assert 'temperature' not in request and 'tool_choice' not in request


def test_gpt6_reasoning_reaches_litellm_parameter_mapping(monkeypatch):
    from litellm.utils import get_optional_params

    monkeypatch.setenv('AI_REASONING_ENABLED', 'true')
    monkeypatch.setenv('AI_REASONING_EFFORT', 'none')
    tools = [{'type': 'function', 'function': {'name': 'echo_probe', 'parameters': {'type': 'object', 'properties': {}}}}]
    request = build_litellm_kwargs(model_name='openai/gpt-6-sol', messages=[], tools=tools)
    # Exercise the installed LiteLLM validator without sending a network request.
    mapped = get_optional_params(
        model='gpt-6-sol', custom_llm_provider='openai',
        reasoning_effort=request['reasoning_effort'], tools=request['tools'],
        allowed_openai_params=request.get('allowed_openai_params'),
    )
    assert mapped['reasoning_effort'] == 'none'
    assert mapped['tools'] == tools


def test_tool_reasoning_override_does_not_change_plain_requests_or_other_providers(monkeypatch):
    monkeypatch.setenv('AI_REASONING_ENABLED', 'true')
    monkeypatch.setenv('AI_REASONING_EFFORT', 'low')
    monkeypatch.setenv('AI_TOOL_REASONING_EFFORT', 'none')
    tools = [{'type': 'function', 'function': {'name': 'inspect', 'parameters': {'type': 'object'}}}]
    request = build_litellm_kwargs(model_name='openai/gpt-6-sol', messages=[], tools=tools)
    assert request['reasoning_effort'] == 'none'
    plain = build_litellm_kwargs(model_name='openai/gpt-6-sol', messages=[])
    assert plain['reasoning_effort'] == 'low'
    other = build_litellm_kwargs(model_name='deepseek/deepseek-chat', messages=[], tools=tools)
    assert other.get('reasoning_effort') != 'none'


def test_gpt6_allowlist_preserves_caller_options_and_provider_isolation(monkeypatch):
    monkeypatch.setenv('AI_REASONING_ENABLED', 'true')
    monkeypatch.setenv('AI_REASONING_EFFORT', 'low')
    allowed = ['other_parameter']
    request = build_litellm_kwargs(model_name='openai/gpt-6.1-sol', messages=[], allowed_openai_params=allowed)
    assert request['allowed_openai_params'] == ['other_parameter', 'reasoning_effort']
    assert allowed == ['other_parameter']
    assert 'allowed_openai_params' not in build_litellm_kwargs(model_name='openai/gpt-5', messages=[])
    assert 'allowed_openai_params' not in build_litellm_kwargs(model_name='anthropic/claude-sonnet-4-6', messages=[])


@pytest.mark.parametrize('name,value', [('AI_TIMEOUT','0'), ('AI_MAX_TOKENS','-1')])
def test_invalid_limits_rejected(monkeypatch,name,value):
    monkeypatch.setenv(name,value)
    with pytest.raises(ValueError):
        get_ai_settings()


def test_base_url_requires_root_and_azure_version(monkeypatch):
    monkeypatch.setenv('AZURE_API_VERSION','test-version')
    assert build_litellm_kwargs(model_name='azure/deployment',messages=[])['api_version'] == 'test-version'
    monkeypatch.setenv('AI_BASE_URL','https://example.test/v1/chat/completions/')
    with pytest.raises(ValueError,match='base URL'):
        get_ai_settings()


@pytest.mark.parametrize('model', ['anthropic/claude-sonnet-4-6','gemini/gemini-2.5-flash','deepseek/deepseek-reasoner','dashscope/qwen-plus'])
def test_tool_roundtrip_preserves_provider_state(monkeypatch,model):
    monkeypatch.setenv('AI_API_KEY','offline-test-key')
    tool = {
        'id': 'call-1',
        'type': 'function',
        'function': {'name':'inspect_raster','arguments':{'raster_id':1}},
        'provider_specific_fields': {'thought_signature':'signature'},
    }
    message = {
        'role': 'assistant',
        'content': [{'type':'text','text':'Checking'}],
        'tool_calls': [tool],
        'reasoning_content': 'opaque reasoning',
        'thinking_blocks': [{'type':'thinking','signature':'signed-state'}],
    }
    messages=[{'role':'user','content':'Inspect raster 1'}]
    calls=[]
    async def completion(**request):
        calls.append(request)
        if len(calls)==1:
            return {'choices':[{'message':message}]}
        assert request['messages'][1]['tool_calls'][0]['function']['arguments'] == '{"raster_id": 1}'
        assert request['messages'][1]['tool_calls'][0]['provider_specific_fields']['thought_signature']=='signature'
        assert request['messages'][1]['thinking_blocks']==message['thinking_blocks']
        assert request['messages'][1]['reasoning_content']==message['reasoning_content']
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Done'))])
    async def run():
        first=await call_chat_completion(model_name=model,messages=messages,tools=[{'type':'function','function':{'name':'inspect_raster','parameters':{'type':'object'}}}],completion_func=completion)
        answer=completion_message(first)
        messages.append(assistant_message(answer,answer['tool_calls']))
        messages.append({'role':'tool','tool_call_id':'call-1','content':'{"ok":true}'})
        second=await call_chat_completion(model_name=model,messages=messages,completion_func=completion)
        assert message_content(completion_message(second))=='Done'
    asyncio.run(run())
