from services.ai_gateway.agent_handler import AgentRequestPayload, _build_agent_system_prompt
from services.ai_gateway.llm_engine import _build_system_prompt
from services.ai_gateway.schema_validator import AILanguage, DataType, TaskMode


def test_spanish_is_accepted_for_agent_and_analysis_prompts():
    payload = AgentRequestPayload(user_prompt="Analiza este ráster", language="es")

    assert payload.language is AILanguage.ES
    assert "Respond in Spanish" in _build_agent_system_prompt(payload.language)
    assert "Respond in Spanish" in _build_system_prompt(
        TaskMode.ANALYZE,
        DataType.RASTER,
        payload.language,
        "{}",
    )


def test_japanese_and_chinese_prompts_use_the_requested_language():
    assert "Respond in Japanese" in _build_agent_system_prompt(AILanguage.JA)
    assert "Respond in Simplified Chinese" in _build_agent_system_prompt(AILanguage.ZH)
