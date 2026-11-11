from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.ai_gateway import agent_session, agent_state_store
from services.ai_gateway.agent_progress import get_agent_progress
from services.ai_gateway.router import router


def test_progress_is_scoped_and_does_not_expose_prompts_or_tool_arguments():
    agent_session.begin_session_turn("chat", "private user prompt", "request", [])
    agent_session.checkpoint_workflow(
        "chat",
        {
            "stage": "executing",
            "round": 1,
            "model_calls": 3,
            "tool_calls": 2,
            "plan": {
                "tasks": [
                    {
                        "id": "coast",
                        "title": "Extract coastline",
                        "instruction": "private instruction",
                    }
                ]
            },
            "completed_tasks": {},
            "events": [{"agent": "executor", "task_id": "coast"}],
        },
    )
    agent_session.checkpoint_agent_activity(
        "chat",
        {
            "role": "executor",
            "task_id": "coast",
            "phase": "tool",
            "tool": "run_script_sandbox",
            "arguments": "private script",
        },
    )
    # Read through durable storage, as a different gateway process would.
    agent_session._AGENT_SESSIONS.clear()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/ai/agent/chat/progress?request_id=request")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        progress = response.json()
        assert progress["status"] == "running"
        assert progress["tool"] == "run_script_sandbox"
        assert progress["task_title"] == "Extract coastline"
        assert progress["round"] == 1
        assert "private" not in response.text
        assert client.get("/ai/agent/chat/progress?request_id=other").json()["status"] == "waiting"
        assert (
            client.get("/ai/agent/other/progress?request_id=request").json()["status"] == "waiting"
        )
        assert client.get("/ai/agent/chat/progress").status_code == 422


def test_resumed_request_clears_failure_and_stale_activity():
    agent_session.begin_session_turn("chat", "Extract coastline", "request", [])
    agent_session.checkpoint_agent_activity("chat", {"phase": "tool", "tool": "old_tool"})
    agent_session.interrupted_turn("chat", "request", "timeout")
    assert get_agent_progress("chat", "request")["status"] == "interrupted"
    agent_session.begin_session_turn("chat", "Extract coastline", "request", [])
    progress = get_agent_progress("chat", "request")
    assert progress["status"] == "running"
    assert progress["tool"] == ""


def test_completed_request_has_only_public_completion_status():
    agent_state_store.save_state(
        "chat",
        {"pending": None},
        {
            "status": "success",
            "answer": "private answer",
            "workflow": {"model_calls": 6, "tool_calls": 3},
        },
        request_id="request",
    )
    progress = get_agent_progress("chat", "request")
    assert progress["status"] == "success"
    assert progress["phase"] == "complete"
    assert progress["model_calls"] == 6
    assert "answer" not in progress
