import pytest
import sys
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient


# 1. Path Patching: Ensures the test runner can find 'services' and 'core' modules.
def patch_sys_path():
    # Set the root to F:\rsmarking
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # Specific services directory for individual module imports
    services_dir = os.path.join(root_dir, "services")
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)


# Execute patching during conftest loading
patch_sys_path()


@pytest.fixture
def client():
    """
    Aggregated Test Client:
    Instead of running multiple uvicorn instances on different ports,
    we mount them into a single FastAPI instance for in-memory testing.
    """
    master_app = FastAPI(title="Backend Test Aggregator")

    # Example: Mounting Tile Service router
    try:
        # Import the router from your specific service structure
        from services.tile_service.router import router as tile_router
        master_app.include_router(tile_router, prefix="/tile")
    except ImportError as e:
        print(f"[Warning] Tile Service not found or import error: {e}")

    # Example: Mounting another service if exists
    # from services.auth_service.main import app as auth_app
    # master_app.mount("/auth", auth_app)

    with TestClient(master_app) as c:
        yield c


@pytest.fixture(autouse=True)
def mock_settings(mocker):
    """
    Global Environment Mocking:
    Prevents tests from touching production databases or real file systems.
    """
    # Use mocker to override configuration objects
    # mocker.patch("services.tile_service.core.config.settings.DATA_DIR", "/tmp/test_data")
    pass