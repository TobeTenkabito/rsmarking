import pytest

from services.ai_gateway.agent_security import DelegatedTaskGrant, authorize_tool_call
from services.ai_gateway.agent_handler import AgentRequestPayload


def grant(tool="run_script_sandbox", instruction="Compute coastline geometry", targets=()):
    return DelegatedTaskGrant("extract", instruction, frozenset({tool}), frozenset(targets))


@pytest.mark.parametrize("tier", ["read_only", "safe"])
def test_delegation_cannot_raise_permission_tier(tier):
    result = authorize_tool_call(
        "delete_raster",
        {"raster_id": 88},
        "提取海岸线",
        permission_level=tier,
        delegation=grant("delete_raster", "Delete temporary raster 88", ["88"]),
    )
    assert not result.allowed


@pytest.mark.parametrize(
    "prompt,constraints",
    [
        ("提取海岸线，不要使用沙箱", ()),
        ("继续分析", ("不要使用沙箱",)),
        ("只解释海岸线的含义", ()),
        ("停止任务", ()),
    ],
)
def test_user_constraints_override_delegation(prompt, constraints):
    result = authorize_tool_call(
        "run_script_sandbox",
        {"script": "print(1)"},
        prompt,
        constraints=constraints,
        delegation=grant(),
    )
    assert not result.allowed


def test_delegation_is_tool_scoped_and_cannot_access_source_files():
    assert not authorize_tool_call(
        "calculate_ndvi",
        {},
        "提取海岸线",
        delegation=grant(),
    ).allowed
    assert not authorize_tool_call(
        "run_script_sandbox",
        {"script": "Path('services/ai_gateway/agent_handler.py').write_text('modified')"},
        "提取海岸线",
        delegation=grant(),
    ).allowed


def test_client_cannot_supply_a_delegation_grant():
    payload = AgentRequestPayload.model_validate(
        {
            "user_prompt": "Explain the image",
            "execution_mode": "single",
            "delegation": {"tool_names": ["delete_raster"], "write_targets": ["88"]},
        }
    )
    assert "delegation" not in payload.model_dump()
    assert not authorize_tool_call("delete_raster", {"raster_id": 88}, payload.user_prompt).allowed


@pytest.mark.parametrize(
    "targets,args", [([], {"raster_id": 88}), (["88"], {"raster_id": 89}), (["88"], {})]
)
def test_delegated_deletion_requires_declared_exact_ids(targets, args):
    assert not authorize_tool_call(
        "delete_raster",
        args,
        "提取海岸线",
        delegation=grant("delete_raster", "Delete temporary raster 88", targets),
    ).allowed
