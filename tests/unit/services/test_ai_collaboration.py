import asyncio
import copy
import json

import pytest

from services.ai_gateway import agent_handler as handler
from services.ai_gateway import agent_session, conversation_archive
from services.ai_gateway.agent_collaboration import AgentPlan


def response(content="", tool=None, arguments=None):
    message = {"content": content, "tool_calls": []}
    if tool:
        message["tool_calls"] = [
            {
                "id": "call-test",
                "type": "function",
                "function": {"name": tool, "arguments": json.dumps(arguments or {})},
            }
        ]
    return {"choices": [{"message": message}]}


def plan(*, tasks=None, description="Output is a non-empty coastline in the requested area"):
    result = {
        "action": "plan",
        "tasks": tasks
        or [
            {
                "id": "coastline",
                "title": "Extract coastline",
                "instruction": "Inspect the input and extract coastline geometry; retain the output id.",
                "depends_on": [],
                "tool_names": ["run_script_sandbox"],
            }
        ],
        "criteria": [{"id": "geometry", "description": description}],
    }
    for task in result["tasks"]:
        task.setdefault("inputs", ["Selected image and recorded dependency outputs"])
        task.setdefault("expected_output", "Stored output id and geometry inspection data")
        task.setdefault("acceptance_ids", ["geometry"])
    return result


def review(evidence="evidence-2", *, accepted=True):
    return {
        "accepted": accepted,
        "summary": "Coastline geometry checked" if accepted else "Output is still a water mask",
        "checks": [
            {
                "criterion_id": "geometry",
                "passed": accepted,
                "evidence_step_ids": [evidence],
                "reason": "Inspected actual output metadata",
            }
        ],
        "issues": [] if accepted else ["Produce line geometry, not a raster mask"],
    }


def request(**kwargs):
    return handler.AgentRequestPayload(
        user_prompt="帮我提取海岸线",
        session_id="coastline-chat",
        request_id="coastline-request",
        language="zh",
        include_workspace_context=False,
        include_archive_memory=False,
        allow_task_steps=True,
        **kwargs,
    )


def run(payload):
    return asyncio.run(handler.handle_agent(payload, object(), object(), "offline-model"))


def mock_model(monkeypatch, responses):
    calls, invocations = [], []

    async def complete(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def invoke(name, arguments, *args):
        invocations.append((name, arguments))
        return {
            "status": "success",
            "result": {
                "new_index_id": 88,
                "geometry_type": "LineString",
                "feature_count": 3,
            },
        }

    monkeypatch.setattr(handler, "call_chat_completion", complete)
    monkeypatch.setattr(handler, "_invoke_agent_tool", invoke)
    return calls, invocations


def execution(script="print('coastline')"):
    return [
        response(tool="run_script_sandbox", arguments={"script": script}),
        response("Created output 88"),
    ]


def verification(evidence="evidence-2", *, accepted=True):
    return [
        response(tool="get_raster_metadata", arguments={"raster_id": 88}),
        response(json.dumps(review(evidence, accepted=accepted))),
    ]


def test_default_collaboration_inspects_executes_and_independently_accepts(monkeypatch):
    responses = [
        response(tool="list_rasters"),
        response(json.dumps(plan())),
        *execution(),
        *verification("evidence-3"),
    ]
    calls, invocations = mock_model(monkeypatch, responses)
    result = run(request())
    assert result["status"] == "success", result
    assert [name for name, _ in invocations] == [
        "list_rasters",
        "run_script_sandbox",
        "get_raster_metadata",
    ]
    assert [step["agent_role"] for step in result["steps"]] == ["planner", "executor", "verifier"]
    assert result["workflow"]["review"]["accepted"]
    assert result["workflow"]["model_calls"] == 6
    assert "completed_tasks" not in result["workflow"]
    assert "planning agent" in calls[0]["messages"][0]["content"]
    assert "execution agent" in calls[2]["messages"][0]["content"]
    assert "independent acceptance agent" in calls[4]["messages"][0]["content"]
    assert all(
        handler._tool_effect(tool["function"]["name"]) == "read" for tool in calls[4]["tools"]
    )
    assert not any(message["role"] == "assistant" for message in calls[4]["messages"])
    assert run(request()) == result
    assert len(calls) == 6


def test_rejected_review_returns_to_planner_and_repairs_once(monkeypatch):
    calls, invocations = mock_model(
        monkeypatch,
        [
            response(json.dumps(plan())),
            *execution(),
            *verification(accepted=False),
            response(json.dumps(plan())),
            *execution("print('repaired lines')"),
            *verification("evidence-4"),
        ],
    )
    result = run(request())
    assert result["status"] == "success", result
    assert result["workflow"]["round"] == 1
    assert sum(name == "run_script_sandbox" for name, _ in invocations) == 2
    assert "Produce line geometry" in json.dumps(calls[5]["messages"])
    assert [
        event["status"] for event in result["workflow"]["events"] if event["agent"] == "verifier"
    ] == ["running", "rejected", "running", "accepted"]


def test_second_rejection_stops_without_infinite_replanning(monkeypatch):
    calls, _ = mock_model(
        monkeypatch,
        [
            response(json.dumps(plan())),
            *execution(),
            *verification(accepted=False),
            response(json.dumps(plan())),
            *execution("print('attempt 2')"),
            *verification("evidence-4", accepted=False),
        ],
    )
    result = run(request())
    assert result["status"] == "not_accepted"
    assert result["workflow"]["round"] == 1
    assert len(calls) == 10


@pytest.mark.parametrize("evidence", ["invented", "evidence-1"])
def test_worker_claims_and_fabricated_evidence_cannot_pass_review(monkeypatch, evidence):
    mock_model(monkeypatch, [response(json.dumps(plan())), *execution(), *verification(evidence)])
    result = run(request(max_replans=0))
    assert result["status"] == "not_accepted"
    assert not result["workflow"]["review"]["accepted"]


def test_reviewer_cannot_execute_repairs_or_elevate_permissions(monkeypatch):
    _, invocations = mock_model(
        monkeypatch,
        [
            response(json.dumps(plan())),
            *execution(),
            response(
                tool="run_script_sandbox",
                arguments={"script": "print('unauthorized review write')"},
            ),
            response(json.dumps(review())),
        ],
    )
    result = run(request(max_replans=0))
    assert result["status"] == "not_accepted"
    assert len(invocations) == 1
    assert result["steps"][-1]["status"] == "error"


def test_reading_chat_references_is_not_independent_output_verification(monkeypatch):
    mock_model(
        monkeypatch,
        [
            response(json.dumps(plan())),
            *execution(),
            response(tool="read_session_context", arguments={"query": "Created output"}),
            response(json.dumps(review())),
        ],
    )
    result = run(request(max_replans=0))
    assert result["status"] == "not_accepted"
    assert result["steps"][-1]["status"] == "success"


def test_explicit_sandbox_prohibition_still_applies_to_worker(monkeypatch):
    _, invocations = mock_model(
        monkeypatch, [response(json.dumps(plan())), *execution(), *verification(accepted=False)]
    )
    payload = request(max_replans=0).model_copy(update={"user_prompt": "提取海岸线，不要使用沙箱"})
    result = run(payload)
    assert result["status"] == "not_accepted"
    assert all(name != "run_script_sandbox" for name, _ in invocations)


@pytest.mark.parametrize(
    "limits,expected_calls",
    [
        ({"max_model_calls": 3}, 3),
        ({"max_tool_calls": 1}, 4),
        ({"agent_token_budget": 8192}, 0),
    ],
)
def test_all_agents_share_a_hard_budget(monkeypatch, limits, expected_calls):
    calls, _ = mock_model(
        monkeypatch, [response(json.dumps(plan())), *execution(), *verification()]
    )
    result = run(request(**limits))
    assert result["status"] == "budget_exhausted", result
    assert len(calls) == expected_calls
    assert not result["workflow"].get("review")


def test_default_workflow_continues_past_previous_call_and_token_limits(monkeypatch):
    from services.ai_gateway.agent_collaboration import (
        new_workflow,
        reserve_model_call,
        workflow_report,
    )

    payload = request()
    assert payload.max_steps is None
    assert payload.max_tool_calls is None
    assert payload.max_model_calls is None
    assert payload.agent_token_budget is None

    responses = [response(json.dumps(plan()))]
    for index in range(33):
        responses.append(
            response(
                tool="run_script_sandbox",
                arguments={"script": f"print('operation {index}')"},
            )
        )
    responses.extend([response("Created output 88"), *verification("evidence-34")])
    calls, invocations = mock_model(monkeypatch, responses)

    result = run(payload)

    assert result["status"] == "success", result
    assert len(calls) == 37
    assert len(invocations) == 34
    assert result["workflow"]["tool_calls"] == 34
    assert result["workflow"]["limits"]["max_tool_calls"] is None

    workflow = new_workflow(payload)
    reserve_model_call(workflow, 1_100_000, 4096)
    assert workflow_report(workflow)["estimated_tokens"] == 1_104_096


def test_resume_preserves_completed_workers_and_cumulative_budget(monkeypatch):
    calls, invocations = mock_model(
        monkeypatch,
        [
            response(json.dumps(plan())),
            *execution(),
            RuntimeError("review model timeout"),
            *verification(),
        ],
    )
    payload = request()
    interrupted = run(payload)
    assert interrupted["status"] == "interrupted"
    assert interrupted["workflow"]["stage"] == "reviewing"
    assert interrupted["workflow"]["model_calls"] == 4
    agent_session._AGENT_SESSIONS.clear()
    result = run(payload)
    assert result["status"] == "success", result
    assert result["workflow"]["model_calls"] == 6
    assert sum(name == "run_script_sandbox" for name, _ in invocations) == 1
    assert "independent acceptance agent" in calls[4]["messages"][0]["content"]


def test_repeated_timeouts_cannot_reset_budget(monkeypatch):
    calls, _ = mock_model(monkeypatch, [RuntimeError("timeout")] * 3)
    payload = request(max_model_calls=3)
    for count in range(3):
        result = run(payload)
        assert result["status"] == "interrupted"
        assert result["workflow"]["model_calls"] == count + 1
        agent_session._AGENT_SESSIONS.clear()
    assert run(payload)["status"] == "budget_exhausted"
    assert len(calls) == 3


def test_review_evidence_survives_timeout_before_review_handoff(monkeypatch):
    _, invocations = mock_model(
        monkeypatch,
        [
            response(json.dumps(plan())),
            *execution(),
            response(tool="get_raster_metadata", arguments={"raster_id": 88}),
            RuntimeError("timeout after inspection"),
            response(json.dumps(review())),
        ],
    )
    payload = request()
    assert run(payload)["status"] == "interrupted"
    agent_session._AGENT_SESSIONS.clear()
    result = run(payload)
    assert result["status"] == "success", result
    assert len(invocations) == 2


@pytest.mark.parametrize(
    "handoff",
    [
        "not json",
        json.dumps(
            plan(
                tasks=[
                    {
                        "id": "fake",
                        "title": "Fake",
                        "instruction": "invent a tool",
                        "tool_names": ["nonexistent_tool"],
                    }
                ]
            )
        ),
    ],
)
def test_invalid_or_unavailable_plan_never_executes(monkeypatch, handoff):
    _, invocations = mock_model(monkeypatch, [response(handoff)])
    result = run(request())
    assert result["status"] == "not_accepted"
    assert not invocations


def test_repair_cannot_weaken_acceptance_criteria(monkeypatch):
    calls, invocations = mock_model(
        monkeypatch,
        [
            response(json.dumps(plan())),
            *execution(),
            *verification(accepted=False),
            response(json.dumps(plan(description="Any non-empty water raster is sufficient"))),
        ],
    )
    result = run(request())
    assert result["status"] == "not_accepted"
    assert len(calls) == 6
    assert len(invocations) == 2


def test_parent_selects_multiple_workers_and_passes_dependencies(monkeypatch):
    tasks = [
        {
            "id": "mask",
            "title": "Water mask",
            "instruction": "Create water mask",
            "tool_names": ["run_script_sandbox"],
        },
        {
            "id": "coast",
            "title": "Coastline",
            "instruction": "Extract lines from the mask",
            "depends_on": ["mask"],
            "tool_names": ["run_script_sandbox"],
        },
    ]
    calls, _ = mock_model(
        monkeypatch,
        [
            response(json.dumps(plan(tasks=tasks))),
            *execution("print('mask')"),
            *execution("print('lines')"),
            *verification("evidence-3"),
        ],
    )
    result = run(request())
    assert result["status"] == "success", result
    assert [step["task_id"] for step in result["steps"]] == ["mask", "coast", "review"]
    assert "Created output 88" in json.dumps(calls[3]["messages"])
    with pytest.raises(ValueError, match="depend only on earlier"):
        AgentPlan.model_validate(plan(tasks=list(reversed(tasks))))


def test_simple_question_uses_only_planner_without_spawning_workers(monkeypatch):
    calls, invocations = mock_model(
        monkeypatch,
        [
            response(
                json.dumps(
                    {"action": "answer", "answer": "A coastline is the land-water boundary."}
                )
            )
        ],
    )
    result = run(request().model_copy(update={"user_prompt": "海岸线是什么意思"}))
    assert result["status"] == "success"
    assert len(calls) == 1
    assert not invocations


def test_missing_input_returns_specific_question_without_execution(monkeypatch):
    _, invocations = mock_model(
        monkeypatch,
        [
            response(
                json.dumps(
                    {"action": "clarify", "answer": "Which image covers the requested coast?"}
                )
            )
        ],
    )
    result = run(request(tool_names=[]))
    assert result["status"] == "needs_input"
    assert not invocations


def test_workflow_report_survives_export_import_without_restoring_authority(monkeypatch, tmp_path):
    monkeypatch.setattr(conversation_archive, "ARCHIVE_DIR", str(tmp_path / "archives"))
    mock_model(monkeypatch, [response(json.dumps(plan())), *execution(), *verification()])
    result = run(request())
    saved = conversation_archive.archive_conversation(
        conversation_archive.ConversationArchiveRequest(
            session_id="coastline-chat",
            messages=[
                {"role": "assistant", "content": result["answer"], "workflow": result["workflow"]}
            ],
        )
    )
    bundle = conversation_archive.export_conversation(saved["archive_id"])
    imported = conversation_archive.import_conversation(
        conversation_archive.ConversationImportRequest.model_validate(bundle)
    )
    restored = conversation_archive.get_conversation_archive(imported["archive_id"])
    assert restored["messages"][0]["workflow"]["review"]["accepted"]
    agent_session.restore_session_messages(imported["session_id"], restored["messages"])
    snapshot = agent_session.get_context_snapshot(imported["session_id"])
    assert snapshot["pending"] is None
    assert not agent_session.get_session_task_scope(imported["session_id"])
    bundle["conversation"]["messages"][0]["workflow"]["events"] = [None]
    with pytest.raises(ValueError):
        conversation_archive.ConversationImportRequest.model_validate(bundle)


def test_plan_cannot_exceed_agent_limit(monkeypatch):
    tasks = [
        {
            "id": "first",
            "title": "First",
            "instruction": "First task",
            "tool_names": ["run_script_sandbox"],
        },
        {
            "id": "second",
            "title": "Second",
            "instruction": "Second task",
            "tool_names": ["run_script_sandbox"],
        },
    ]
    _, invocations = mock_model(monkeypatch, [response(json.dumps(plan(tasks=tasks)))])
    assert run(request(max_agents=3))["status"] == "not_accepted"
    assert not invocations


@pytest.mark.parametrize(
    "tool,instruction,arguments,targets",
    [
        (
            "calculate_ndvi",
            "Compute NDVI as an intermediate coastline analysis",
            {"red_id": 1, "nir_id": 2},
            [],
        ),
        (
            "update_vector_layer",
            "Rename the output vector layer to Coastline",
            {"layer_id": "11111111-1111-4111-8111-111111111111", "name": "Coastline"},
            ["11111111-1111-4111-8111-111111111111"],
        ),
        (
            "delete_raster",
            "Delete temporary raster 88 after coastline extraction",
            {"raster_id": 88},
            ["88"],
        ),
    ],
)
def test_validated_parent_assignment_authorizes_derived_operations(
    monkeypatch, tool, instruction, arguments, targets
):
    from services.ai_gateway.agent_security import authorize_tool_call

    assert not authorize_tool_call(tool, arguments, "帮我提取海岸线").allowed
    assignment = plan(
        tasks=[
            {
                "id": "derived",
                "title": "Derived task",
                "instruction": instruction,
                "tool_names": [tool],
                "write_targets": targets,
            }
        ]
    )
    calls, invocations = mock_model(
        monkeypatch,
        [
            response(json.dumps(assignment)),
            response(tool=tool, arguments=arguments),
            response("Derived operation completed"),
            *verification(),
        ],
    )
    result = run(request().model_copy(update={"allow_task_steps": False}))
    assert result["status"] == "success", result
    assert invocations[0] == (tool, arguments)
    assert result["steps"][0]["authorization_source"] == "delegated_task"
    delegated = next(
        message
        for message in calls[1]["messages"]
        if isinstance(message.get("content"), str)
        and message["content"].startswith("[Server-validated delegated assignment")
    )
    assert instruction in delegated["content"]
    assert "BEGIN_UNTRUSTED_DATA_" not in delegated["content"]
    assert "expected_output" in delegated["content"]


def test_delegated_mutation_cannot_escape_exact_targets(monkeypatch):
    assignment = plan(
        tasks=[
            {
                "id": "cleanup",
                "title": "Cleanup",
                "instruction": "Delete temporary raster 88",
                "tool_names": ["delete_raster"],
                "write_targets": ["88"],
            }
        ]
    )
    _, invocations = mock_model(
        monkeypatch,
        [
            response(json.dumps(assignment)),
            response(tool="delete_raster", arguments={"raster_id": 89}),
            response("Could not delete the unassigned raster"),
            *verification(accepted=False),
        ],
    )
    result = run(request(max_replans=0))
    assert result["steps"][0]["status"] == "error"
    assert "exact ids" in result["steps"][0]["error"]
    assert all(name != "delete_raster" for name, _ in invocations)


@pytest.mark.parametrize("field", ["inputs", "expected_output", "acceptance_ids"])
def test_vague_task_assignments_are_rejected(field):
    assignment = plan()
    del assignment["tasks"][0][field]
    with pytest.raises(ValueError):
        AgentPlan.model_validate(assignment)


def test_provider_usage_replaces_conservative_call_reservations(monkeypatch):
    responses = [response(json.dumps(plan())), *execution(), *verification()]
    for item in responses:
        item["usage"] = {"total_tokens": 100}
    mock_model(monkeypatch, responses)
    result = run(request())
    assert result["status"] == "success"
    assert result["workflow"]["estimated_tokens"] == 500


def test_resume_keeps_completed_review_rounds_and_goes_directly_to_final_handoff(monkeypatch):
    calls, _ = mock_model(
        monkeypatch,
        [
            response(json.dumps(plan())),
            *execution(),
            response(tool="get_raster_metadata", arguments={"raster_id": 88}),
            response(tool="get_raster_statistics", arguments={"raster_id": 88}),
            RuntimeError("final review response timeout"),
            response(json.dumps(review("evidence-3"))),
        ],
    )
    payload = request(max_steps=2)
    assert run(payload)["status"] == "interrupted"
    result = run(payload)
    assert result["status"] == "success", result
    assert not calls[-1].get("tools")
    assert "evidence-3" in json.dumps(calls[-1]["messages"])
    assert len(result["steps"]) == 3


def test_original_sandbox_script_is_recoverable_after_context_compaction(monkeypatch):
    from services.ai_gateway import agent_state_store

    script = "print('repairable original script')"
    mock_model(monkeypatch, [response(json.dumps(plan())), *execution(script), *verification()])
    result = run(request())
    reference = result["steps"][0]["result"]["script_reference"]
    stored = agent_state_store.read_resource("coastline-chat", reference)
    assert script in stored["text"]
    assert "repairable original script" not in json.dumps(result["steps"][0]["arguments"])


def test_resume_before_any_operation_allows_fixing_a_new_failed_script(monkeypatch):
    calls, _ = mock_model(
        monkeypatch,
        [
            RuntimeError("initial model timeout"),
            response(json.dumps(plan())),
            response(tool="run_script_sandbox", arguments={"script": "print('bad shape')"}),
            response(tool="run_script_sandbox", arguments={"script": "print('fixed shape')"}),
            response("Created output 88"),
            *verification("evidence-3"),
        ],
    )
    invocations = []

    async def invoke(name, arguments, *args):
        invocations.append((name, arguments))
        if "bad shape" in arguments.get("script", ""):
            return {"status": "error", "error": "array shape mismatch"}
        return {"status": "success", "result": {"id": 88, "geometry_type": "LineString"}}

    monkeypatch.setattr(handler, "_invoke_agent_tool", invoke)
    payload = request()
    assert run(payload)["status"] == "interrupted"
    result = run(payload)
    assert result["status"] == "success", result
    assert len(invocations) == 3
    assert "fixed shape" in invocations[1][1]["script"]


@pytest.mark.parametrize("field", ["title", "instruction", "expected_output"])
def test_blank_assignment_text_is_rejected(field):
    assignment = plan()
    assignment["tasks"][0][field] = "   "
    with pytest.raises(ValueError):
        AgentPlan.model_validate(assignment)
