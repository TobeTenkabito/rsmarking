import asyncio
import json
from types import SimpleNamespace

import pytest

from services.ai_gateway import agent_handler
from services.ai_gateway.agent_handler import AgentRequestPayload, handle_agent


def _run(awaitable):
    return asyncio.run(awaitable)


def _message(content="", tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def _response(content="", tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=_message(content, tool_calls))])


def _tool_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments),
        ),
    )


def test_agent_returns_direct_answer_without_tool_calls(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _response("No tool needed.")

    monkeypatch.setattr(agent_handler, "acompletion", fake_acompletion)
    monkeypatch.setattr(agent_handler, "_get_agent_tools", lambda names: [{"type": "function"}])
    monkeypatch.setattr(agent_handler, "_get_allowed_tool_names", lambda names: {"calculate_ndvi"})

    result = _run(
        handle_agent(
            AgentRequestPayload(user_prompt="Explain this briefly.", language="en"),
            db=object(),
            vector_db=object(),
            model_name="test-model",
        )
    )

    assert result["status"] == "success"
    assert result["mode"] == "agent"
    assert result["answer"] == "No tool needed."
    assert result["steps"] == []
    assert calls[0]["model"] == "test-model"
    assert calls[0]["tools"]


def test_agent_invokes_registered_tool_and_returns_trace(monkeypatch):
    calls = []
    responses = [
        _response(
            tool_calls=[
                _tool_call(
                    "calculate_ndvi",
                    {"red_id": 1, "nir_id": 2, "new_name": "ndvi_agent.tif"},
                )
            ]
        ),
        _response("Created NDVI output."),
    ]

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    async def fake_invoke_registered_function(request, db, vector_db):
        assert request.name == "calculate_ndvi"
        return {
            "status": "success",
            "name": request.name,
            "result": {"new_index_id": 99, "file_name": request.arguments["new_name"]},
        }

    monkeypatch.setattr(agent_handler, "acompletion", fake_acompletion)
    monkeypatch.setattr(agent_handler, "_get_agent_tools", lambda names: [{"type": "function"}])
    monkeypatch.setattr(agent_handler, "_get_allowed_tool_names", lambda names: {"calculate_ndvi"})

    async def fake_invoke_agent_tool(name, arguments, db, vector_db):
        request = SimpleNamespace(name=name, arguments=arguments)
        return await fake_invoke_registered_function(request, db, vector_db)

    monkeypatch.setattr(agent_handler, "_invoke_agent_tool", fake_invoke_agent_tool)

    result = _run(
        handle_agent(
            AgentRequestPayload(
                user_prompt="Create NDVI from rasters 1 and 2.",
                language="en",
                max_steps=3,
                tool_names=["calculate_ndvi"],
            ),
            db=object(),
            vector_db=object(),
            model_name="test-model",
        )
    )

    assert result["status"] == "success"
    assert result["answer"] == "Created NDVI output."
    assert result["used_tools"] == ["calculate_ndvi"]
    assert result["steps"][0]["status"] == "success"
    assert result["steps"][0]["result"]["result"]["new_index_id"] == 99
    assert any(message["role"] == "tool" for message in calls[1]["messages"])


def test_agent_rejects_unknown_tool_allow_list(monkeypatch):
    def raise_unknown_tool(names):
        raise ValueError("Unknown AI function(s): missing_tool")

    monkeypatch.setattr(agent_handler, "_get_agent_tools", raise_unknown_tool)

    with pytest.raises(ValueError, match="Unknown AI function"):
        _run(
            handle_agent(
                AgentRequestPayload(
                    user_prompt="Try a missing tool.",
                    language="en",
                    tool_names=["missing_tool"],
                ),
                db=object(),
                vector_db=object(),
                model_name="test-model",
            )
        )


def test_agent_registry_wrappers_can_be_restricted(monkeypatch):
    monkeypatch.setattr(
        agent_handler,
        "_get_agent_tools",
        lambda names: [
            {
                "type": "function",
                "function": {"name": names[0], "parameters": {"type": "object"}},
            }
        ],
    )

    tools = agent_handler._get_agent_tools(["calculate_ndvi"])

    assert [tool["function"]["name"] for tool in tools] == ["calculate_ndvi"]
