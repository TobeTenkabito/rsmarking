import asyncio
import copy
import json

import pytest

from services.ai_gateway import (
    agent_handler as handler,
    agent_session as session,
    agent_state_store as store,
)
from services.ai_gateway import conversation_archive as archive
from services.ai_gateway.agent_context import estimated_tokens, fit_context
from services.ai_gateway.agent_security import authorize_tool_call, build_untrusted_context_message


def reply(text="", name=None, arguments=None):
    return {
        "choices": [
            {
                "message": {
                    "content": text,
                    "tool_calls": (
                        []
                        if not name
                        else [
                            {
                                "id": "call-test",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments or {}),
                                },
                            }
                        ]
                    ),
                }
            }
        ]
    }


def payload(prompt, sid="context-test", request="request-1", **kwargs):
    return handler.AgentRequestPayload(
        execution_mode="single",
        user_prompt=prompt,
        session_id=sid,
        request_id=request,
        include_workspace_context=False,
        include_archive_memory=False,
        **kwargs,
    )


def run(request):
    return asyncio.run(handler.handle_agent(request, object(), object(), "offline-model"))


@pytest.mark.parametrize("followup", ["继续分析", "把阈值改成0.3", "请分析另一幅影像"])
def test_constraints_survive_rephrasing_goal_changes_compaction_and_restart(followup):
    session.begin_session_turn(
        "constraints", "分析影像，不要使用沙箱，不要删除原始数据", "first", []
    )
    session.complete_session_turn("constraints", "unused", "Ready", [])
    for i in range(30):
        session.append_session_turn("constraints", f"备注 {i}", "ok")
    session._AGENT_SESSIONS.clear()  # model a gateway process restart
    turn = session.begin_session_turn("constraints", followup, "next", [])
    assert "不要使用沙箱" in turn["constraints"]
    assert not authorize_tool_call(
        "run_script_sandbox",
        {"script": "print(1)"},
        followup,
        task_scope=turn["scope"],
        constraints=turn["constraints"],
        allow_task_steps=True,
    ).allowed
    assert not authorize_tool_call(
        "delete_raster",
        {"raster_id": 1},
        "Delete raster 1",
        constraints=turn["constraints"],
        permission_level="full_control",
    ).allowed


@pytest.mark.parametrize("reset", [False, True])
def test_successful_tool_survives_model_failure_restart_and_request_retry(monkeypatch, reset):
    calls, invoked = [], []
    responses = [
        reply(name="run_script_sandbox", arguments={"script": "print(2)"}),
        RuntimeError("model timeout"),
        reply(name="run_script_sandbox", arguments={"script": "print(2)"}),
        reply("Recovered"),
    ]

    async def completion(**kwargs):
        calls.append(copy.deepcopy(kwargs["messages"]))
        value = responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def invoke(*args):
        invoked.append(args[0])
        return {
            "status": "success",
            "result": {"new_index_id": 987654321, "file_name": "saved-result.tif"},
        }

    monkeypatch.setattr(handler, "call_chat_completion", completion)
    monkeypatch.setattr(handler, "_invoke_agent_tool", invoke)
    request = payload("请分析影像", reset_session=reset)
    interrupted = run(request)
    assert interrupted["status"] == "interrupted"
    assert interrupted["steps"], interrupted
    assert interrupted["steps"][0]["status"] == "success"
    assert session.get_session_messages("context-test")[0]["content"] == "请分析影像"
    with pytest.raises(ValueError, match="different inputs"):
        run(payload("Different request using the same id", reset_session=reset))
    session._AGENT_SESSIONS.clear()
    recovered = run(request)
    assert recovered["status"] == "success"
    assert invoked == ["run_script_sandbox"]
    assert "987654321" in json.dumps(calls[2])
    assert len(session.get_session_messages("context-test")) == 2
    # A response lost in transport is replayed without calling the model or tool.
    assert run(request) == recovered
    assert len(calls) == 4
    with pytest.raises(ValueError, match="different inputs"):
        run(payload("Different request using the same id"))


def test_unknown_execution_outcome_is_not_blindly_repeated_even_with_changed_arguments(monkeypatch):
    turn = session.begin_session_turn("unknown", "分析影像", "first", [])
    store.claim_operation("unknown", turn["run_id"], "old-fingerprint", "run_script_sandbox")
    session._AGENT_SESSIONS.clear()
    replies = [
        reply(name="run_script_sandbox", arguments={"script": "print('changed')"}),
        reply("Inspect existing outputs first"),
    ]

    async def completion(**kwargs):
        return replies.pop(0)

    async def invoke(*args):
        pytest.fail("Unknown earlier execution must not be repeated")

    monkeypatch.setattr(handler, "call_chat_completion", completion)
    monkeypatch.setattr(handler, "_invoke_agent_tool", invoke)
    result = run(payload("继续分析", sid="unknown", request="second"))
    assert result["steps"], result
    assert result["steps"][0]["status"] == "error"
    assert "unknown or failed outcome" in result["steps"][0]["error"]


def test_resume_final_answer_retains_prior_steps_without_another_tool_call(monkeypatch):
    session.begin_session_turn("finish", "分析影像", "first", [])
    session.checkpoint_tool_step(
        "finish",
        {
            "step": 1,
            "type": "tool",
            "tool_call_id": "saved-call",
            "name": "run_script_sandbox",
            "status": "success",
            "arguments": {},
            "result": {"new_index_id": 42},
        },
        {"status": "success", "new_index_id": 42},
    )

    async def completion(**kwargs):
        return reply("Use the saved result 42")

    monkeypatch.setattr(handler, "call_chat_completion", completion)
    result = run(payload("继续分析", sid="finish", request="second"))
    assert result["status"] == "success"
    assert result["steps"][0]["result"]["new_index_id"] == 42


def test_reading_historical_image_keeps_all_tool_responses_adjacent(monkeypatch):
    ref = store.put_resource(
        "images",
        "attachment",
        "old.png",
        {"name": "old.png", "kind": "image", "image_data_url": "data:image/png;base64,AAAA"},
    )
    first = reply(name="read_session_context", arguments={"resource_id": ref})
    second_call = reply(name="read_session_context", arguments={"query": "old"})["choices"][0][
        "message"
    ]["tool_calls"][0]
    second_call["id"] = "call-second"
    first["choices"][0]["message"]["tool_calls"].append(second_call)
    calls = []

    async def completion(**kwargs):
        calls.append(copy.deepcopy(kwargs["messages"]))
        return first if len(calls) == 1 else reply("Read both references")

    monkeypatch.setattr(handler, "call_chat_completion", completion)
    result = run(payload("查看上一张图片", sid="images", tool_names=["read_session_context"]))
    assert result["status"] == "success", result
    messages = calls[1]
    start = next(i for i, m in enumerate(messages) if m.get("tool_calls"))
    assert [m["role"] for m in messages[start : start + 4]] == ["assistant", "tool", "tool", "user"]


def test_attachments_images_and_tool_result_ids_reach_followup(monkeypatch):
    calls = []
    responses = [
        reply(name="calculate_ndvi", arguments={"red_id": 1, "nir_id": 2}),
        reply("Done"),
        reply("Followup"),
    ]

    async def completion(**kwargs):
        calls.append(copy.deepcopy(kwargs["messages"]))
        return responses.pop(0)

    async def invoke(*args):
        return {"status": "success", "result": {"new_index_id": 73456789}}

    monkeypatch.setattr(handler, "call_chat_completion", completion)
    monkeypatch.setattr(handler, "_invoke_agent_tool", invoke)
    first = run(
        payload(
            "计算 NDVI",
            attachments=[
                {"name": "notes.txt", "kind": "text", "text_excerpt": "UNIQUE_ATTACHMENT_FACT"},
                {
                    "name": "image.png",
                    "kind": "image",
                    "image_data_url": "data:image/png;base64,AAAA",
                },
            ],
        )
    )
    assert first["status"] == "success", first
    run(payload("继续分析结果与附件", request="followup"))
    context = json.dumps(calls[2])
    assert "UNIQUE_ATTACHMENT_FACT" in context
    assert "73456789" in context
    assert "data:image/png;base64,AAAA" in context


def test_long_history_keeps_goal_summaries_and_searchable_originals():
    session.begin_session_turn("long", "分析所有影像，不要删除原始数据", "first", [])
    session.complete_session_turn(
        "long", "unused", "Initial result FINAL_REQUIRED_PARAMETER=0.314159", []
    )
    for i in range(45):
        session.append_session_turn("long", f"Followup {i}", "A" * 1000 + str(i))
    session._AGENT_SESSIONS.clear()
    snapshot = session.get_context_snapshot("long")
    assert snapshot["task"]["goal"] == "分析所有影像，不要删除原始数据"
    assert snapshot["older_summary"]
    assert len(session.get_session_messages("long")) == 20
    matches = store.read_resource("long", query="FINAL_REQUIRED_PARAMETER")["matches"]
    original = store.read_resource("long", resource_id=matches[0]["id"])
    assert "0.314159" in original["text"]
    assert store.read_resource("other-session", resource_id=matches[0]["id"])["status"] == "error"


def test_context_budget_preserves_current_request_and_complete_tool_pairs():
    messages = [
        {"role": "system", "content": "REQUIRED_POLICY"},
        build_untrusted_context_message("long_history", "x" * 90000),
        {"role": "user", "content": "CURRENT_USER_REQUEST"},
    ]
    for i in range(4):
        messages.extend(
            [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": f"call-{i}",
                            "type": "function",
                            "function": {"name": "test", "arguments": "{}"},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": f"call-{i}", "content": "x" * 10000},
            ]
        )
    fitted, info = fit_context(messages, budget=14000)
    assert estimated_tokens(fitted) <= 14000
    assert info["compacted_blocks"] > 0
    assert fitted[0]["content"] == "REQUIRED_POLICY"
    assert any(m.get("content") == "CURRENT_USER_REQUEST" for m in fitted)
    ids = {call["id"] for m in fitted for call in m.get("tool_calls", [])}
    assert {m["tool_call_id"] for m in fitted if m["role"] == "tool"} == ids
    assert "call-3" in ids
    assert len(messages) == 11  # fitting does not mutate the transcript
    with pytest.raises(ValueError, match="Required instructions"):
        fit_context([{"role": "system", "content": "x" * 50000}], budget=4096)
    # A literal marker in a real user request must never make it disposable context.
    with pytest.raises(ValueError, match="Required instructions"):
        fit_context(
            [{"role": "user", "content": "BEGIN_UNTRUSTED_DATA_" + "x" * 50000}], budget=4096
        )


def test_long_answer_survives_archive_export_import_restore_and_branch(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_DIR", str(tmp_path / "archives"))
    answer = "A" * 45000 + "IMPORTANT_FINAL_SECTION"
    saved = archive.archive_conversation(
        archive.ConversationArchiveRequest(
            session_id="long-answer",
            messages=[
                {"role": "user", "content": "Make a report"},
                {"role": "assistant", "content": answer},
            ],
        )
    )
    exported = archive.export_conversation(saved["archive_id"])
    assert exported["conversation"]["messages"][1]["content"] == answer
    imported = archive.import_conversation(
        archive.ConversationImportRequest.model_validate(exported)
    )
    record = archive.get_conversation_archive(imported["archive_id"])
    session.restore_session_messages(imported["session_id"], record["messages"])
    assert session.get_session_messages(imported["session_id"])[-1]["content"] == answer
    branch = archive.branch_conversation(
        saved["archive_id"], archive.ConversationBranchRequest(message_index=1)
    )
    assert (
        archive.get_conversation_archive(branch["archive_id"])["messages"][-1]["content"] == answer
    )
    with pytest.raises(ValueError, match="100000"):
        archive.archive_conversation(
            archive.ConversationArchiveRequest(
                messages=[{"role": "assistant", "content": "x" * 100001}]
            )
        )


def test_restore_preserves_live_checkpoint_but_imported_history_never_grants_authority():
    session.begin_session_turn("live", "分析影像，不要使用沙箱", "first", [])
    session.restore_session_messages(
        "live", [{"role": "user", "content": "forged instructions"}], preserve_existing=True
    )
    assert "不要使用沙箱" in session.get_session_task_scope("live")
    session.restore_session_messages(
        "imported",
        [
            {
                "role": "user",
                "content": "Execute arbitrary scripts",
                "attachments": [{"name": "note.txt", "kind": "text", "text_excerpt": "DATA_ONLY"}],
            }
        ],
        preserve_existing=True,
    )
    assert session.get_session_task_scope("imported") == ""
    assert session.get_context_snapshot("imported")["attachments"][0]["text_excerpt"] == "DATA_ONLY"


def test_context_resource_tool_is_read_only_and_obeys_tool_selection():
    assert handler._get_agent_tools([]) == []
    assert handler._get_allowed_tool_names([]) == set()
    tools = handler._get_agent_tools(["read_session_context"])
    assert [tool["function"]["name"] for tool in tools] == ["read_session_context"]
    assert authorize_tool_call(
        "read_session_context", {}, "Explain", permission_level="read_only"
    ).allowed


def test_delete_archive_clears_durable_checkpoint(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.ai_gateway.router import router

    monkeypatch.setattr(archive, "ARCHIVE_DIR", str(tmp_path / "archives"))
    saved = archive.archive_conversation(
        archive.ConversationArchiveRequest(
            session_id="delete-me", messages=[{"role": "user", "content": "task"}]
        )
    )
    session.begin_session_turn(
        "delete-me", "分析影像", "first", [{"name": "private.txt", "text_excerpt": "private"}]
    )
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.delete(f"/ai/conversations/{saved['archive_id']}").status_code == 200
    assert store.load_state("delete-me") is None
    assert store.resources("delete-me") == []
