import os
import sys

import pytest


@pytest.fixture(autouse=True)
def isolated_agent_checkpoints(tmp_path, monkeypatch):
    """Unit tests must never read or write the user's durable chat state."""
    from services.ai_gateway import agent_state_store, agent_session
    from services.ai_gateway import environment_settings
    monkeypatch.setattr(environment_settings, "SETTINGS_PATH", tmp_path / "ai-environment.json")
    monkeypatch.setattr(agent_state_store, "STATE_DB", tmp_path / "agent-state.sqlite3")
    agent_session._AGENT_SESSIONS.clear()
    agent_session._AGENT_SESSION_EXECUTION_LOCKS.clear()
    yield
    agent_session._AGENT_SESSIONS.clear()
    agent_session._AGENT_SESSION_EXECUTION_LOCKS.clear()


def pytest_configure(config):
    """Keep service tests importable when invoked below the repo root."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)


@pytest.fixture
def client():
    """
    In-memory router client for tests that exercise FastAPI endpoints.
    Pure service units should not need FastAPI just to collect.
    """
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")

    FastAPI = fastapi.FastAPI
    TestClient = testclient.TestClient
    master_app = FastAPI(title="Backend Test Aggregator")

    try:
        from services.tile_service.router import router as tile_router
        master_app.include_router(tile_router, prefix="/tile")
    except ImportError as e:
        print(f"[Warning] Tile Service not found or import error: {e}")

    with TestClient(master_app) as c:
        yield c
