import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock as ThreadLock
from types import SimpleNamespace

import pytest

from services.ai_gateway import agent_handler
from services.ai_gateway.agent_session import session_execution_lock
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


def test_agent_reuses_session_history(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response("First answer.")
        return _response("Second answer.")

    async def empty_workspace_context(db, vector_db, limit):
        return ""

    monkeypatch.setattr(agent_handler, "acompletion", fake_acompletion)
    monkeypatch.setattr(agent_handler, "_get_agent_tools", lambda names: [{"type": "function"}])
    monkeypatch.setattr(agent_handler, "_get_allowed_tool_names", lambda names: {"calculate_ndvi"})
    monkeypatch.setattr(agent_handler, "_build_workspace_context", empty_workspace_context)

    first = _run(
        handle_agent(
            AgentRequestPayload(
                user_prompt="Remember this dataset is coastal.",
                language="en",
                session_id="session-memory-test",
                reset_session=True,
            ),
            db=object(),
            vector_db=object(),
            model_name="test-model",
        )
    )
    second = _run(
        handle_agent(
            AgentRequestPayload(
                user_prompt="What did I say about it?",
                language="en",
                session_id="session-memory-test",
            ),
            db=object(),
            vector_db=object(),
            model_name="test-model",
        )
    )

    second_messages = calls[1]["messages"]

    assert first["history_length"] == 2
    assert second["session_id"] == "session-memory-test"
    assert second["history_length"] == 4
    assert {"role": "user", "content": "Remember this dataset is coastal."} in second_messages
    assert {"role": "assistant", "content": "First answer."} in second_messages


def test_agent_serializes_same_session_requests(monkeypatch):
    calls = []
    active_calls = 0
    max_active_calls = 0

    async def fake_acompletion(**kwargs):
        nonlocal active_calls, max_active_calls
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        calls.append(kwargs)
        await asyncio.sleep(0.01)
        active_calls -= 1
        return _response(f"Answer {len(calls)}.")

    async def empty_workspace_context(db, vector_db, limit):
        return ""

    monkeypatch.setattr(agent_handler, "acompletion", fake_acompletion)
    monkeypatch.setattr(agent_handler, "_get_agent_tools", lambda names: [{"type": "function"}])
    monkeypatch.setattr(agent_handler, "_get_allowed_tool_names", lambda names: {"calculate_ndvi"})
    monkeypatch.setattr(agent_handler, "_build_workspace_context", empty_workspace_context)

    async def scenario():
        first_payload = AgentRequestPayload(
            user_prompt="First locked request.",
            language="en",
            session_id="locked-session-test",
            reset_session=True,
        )
        second_payload = AgentRequestPayload(
            user_prompt="Second locked request.",
            language="en",
            session_id="locked-session-test",
        )
        return await asyncio.gather(
            handle_agent(first_payload, db=object(), vector_db=object(), model_name="test-model"),
            handle_agent(second_payload, db=object(), vector_db=object(), model_name="test-model"),
        )

    first, second = _run(scenario())

    assert max_active_calls == 1
    assert first["answer"] == "Answer 1."
    assert second["answer"] == "Answer 2."
    assert {"role": "user", "content": "First locked request."} in calls[1]["messages"]
    assert {"role": "assistant", "content": "Answer 1."} in calls[1]["messages"]


def test_agent_session_lock_serializes_across_event_loops():
    active_calls = 0
    max_active_calls = 0
    guard = ThreadLock()
    start_barrier = Barrier(2)
    session_id = "cross-loop-session-lock-test"

    async def locked_work():
        nonlocal active_calls, max_active_calls
        start_barrier.wait(timeout=5)
        async with session_execution_lock(session_id):
            with guard:
                active_calls += 1
                max_active_calls = max(max_active_calls, active_calls)
            await asyncio.sleep(0.03)
            with guard:
                active_calls -= 1

    def run_worker():
        asyncio.run(locked_work())

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_worker) for _ in range(2)]
        for future in futures:
            future.result(timeout=5)

    assert max_active_calls == 1


def test_agent_includes_archive_memory_context(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _response("I remember the archive.")

    async def empty_workspace_context(db, vector_db, limit):
        return ""

    monkeypatch.setattr(agent_handler, "acompletion", fake_acompletion)
    monkeypatch.setattr(agent_handler, "_get_agent_tools", lambda names: [{"type": "function"}])
    monkeypatch.setattr(agent_handler, "_get_allowed_tool_names", lambda names: {"calculate_ndvi"})
    monkeypatch.setattr(agent_handler, "_build_workspace_context", empty_workspace_context)
    monkeypatch.setattr(agent_handler, "_build_archive_memory_context", lambda limit: "[Conversation Archive Memory]\nremembered")

    _run(
        handle_agent(
            AgentRequestPayload(
                user_prompt="Use what we saved.",
                language="en",
                include_archive_memory=True,
            ),
            db=object(),
            vector_db=object(),
            model_name="test-model",
        )
    )

    assert {"role": "system", "content": "[Conversation Archive Memory]\nremembered"} in calls[0]["messages"]


def test_agent_includes_uploaded_text_attachment_context(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _response("I read the attachment.")

    async def empty_workspace_context(db, vector_db, limit):
        return ""

    monkeypatch.setattr(agent_handler, "acompletion", fake_acompletion)
    monkeypatch.setattr(agent_handler, "_get_agent_tools", lambda names: [{"type": "function"}])
    monkeypatch.setattr(agent_handler, "_get_allowed_tool_names", lambda names: {"calculate_ndvi"})
    monkeypatch.setattr(agent_handler, "_build_workspace_context", empty_workspace_context)

    _run(
        handle_agent(
            AgentRequestPayload(
                user_prompt="Use the attached notes.",
                language="en",
                attachments=[
                    {
                        "name": "notes.md",
                        "kind": "text",
                        "mime_type": "text/markdown",
                        "size": 42,
                        "text_excerpt": "Important project note",
                    }
                ],
            ),
            db=object(),
            vector_db=object(),
            model_name="test-model",
        )
    )

    user_message = next(message for message in calls[0]["messages"] if message["role"] == "user")
    assert "[Uploaded Attachments]" in user_message["content"]
    assert "notes.md" in user_message["content"]
    assert "Important project note" in user_message["content"]


def test_agent_sends_image_attachment_as_multimodal_part(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _response("I can see the attached image.")

    async def empty_workspace_context(db, vector_db, limit):
        return ""

    monkeypatch.setattr(agent_handler, "acompletion", fake_acompletion)
    monkeypatch.setattr(agent_handler, "_get_agent_tools", lambda names: [{"type": "function"}])
    monkeypatch.setattr(agent_handler, "_get_allowed_tool_names", lambda names: {"calculate_ndvi"})
    monkeypatch.setattr(agent_handler, "_build_workspace_context", empty_workspace_context)

    _run(
        handle_agent(
            AgentRequestPayload(
                user_prompt="Inspect this image.",
                language="en",
                attachments=[
                    {
                        "name": "preview.png",
                        "kind": "image",
                        "mime_type": "image/png",
                        "size": 16,
                        "image_data_url": "data:image/png;base64,AAAA",
                        "width": 2,
                        "height": 2,
                    }
                ],
            ),
            db=object(),
            vector_db=object(),
            model_name="test-model",
        )
    )

    user_message = next(message for message in calls[0]["messages"] if message["role"] == "user")
    content = user_message["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert "preview.png" in content[0]["text"]
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,AAAA", "detail": "auto"},
    }


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


def test_agent_sandbox_tool_schema_prefers_indexed_input_variables():
    tools = agent_handler._get_agent_tools(["run_script_sandbox"])
    properties = tools[0]["function"]["parameters"]["properties"]

    assert "input_0" in properties["raster_ids"]["description"]
    assert "actual input_0/input_1" in properties["script"]["description"]
    assert "literal string 'input_file'" in properties["raster_ids"]["description"]


def test_agent_sandbox_error_mentions_indexed_input_variable(monkeypatch):
    from services.ai_gateway import function_registry

    async def failing_invoke(request, db, vector_db):
        raise RuntimeError("Sandbox exited with status code 1")

    monkeypatch.setattr(function_registry, "invoke_registered_function", failing_invoke)

    result = _run(
        agent_handler._invoke_agent_tool(
            "run_script_sandbox",
            {"script": "import rasterio\nwith rasterio.open('input_file') as src:\n    data = src.read(1)"},
            db=object(),
            vector_db=object(),
        )
    )

    assert result["status"] == "error"
    assert "input_0" in result["error"]
    assert "literal string 'input_file'" in result["error"]


def test_agent_system_prompt_mentions_sandbox_fallback():
    prompt = agent_handler._build_agent_system_prompt(agent_handler.AILanguage.EN)

    assert "run_script_sandbox" in prompt
    assert "no dedicated tool" in prompt
    assert "input_0" in prompt
    assert "Do not use the example placeholder input_file" in prompt


def test_agent_session_can_be_restored():
    session_id = "restore-session-test"
    count = agent_handler.restore_session_messages(
        session_id,
        [
            {"role": "system", "content": "ignore"},
            {"role": "user", "content": "Original request"},
            {"role": "assistant", "content": "Original answer"},
        ],
    )

    history = agent_handler.get_session_messages(session_id)

    assert count == 2
    assert history == [
        {"role": "user", "content": "Original request"},
        {"role": "assistant", "content": "Original answer"},
    ]
