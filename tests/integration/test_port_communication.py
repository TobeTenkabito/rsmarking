import os

import httpx
import pytest


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RS_RUN_PORT_TESTS") != "1",
        reason="Set RS_RUN_PORT_TESTS=1 to probe running service ports.",
    ),
]


SERVICE_PORTS = [
    (
        "annotation",
        "RS_PORT_TEST_ANNOTATION_URL",
        "http://localhost:8001",
        "Annotation Service",
    ),
    (
        "data",
        "RS_PORT_TEST_DATA_URL",
        "http://localhost:8002",
        "Raster Processing Service",
    ),
    (
        "vector tile",
        "RS_PORT_TEST_VTILE_URL",
        "http://localhost:8003",
        "Vector Tile Service",
    ),
    (
        "executor",
        "RS_PORT_TEST_EXECUTOR_URL",
        "http://localhost:8004",
        "Executor Service",
    ),
    (
        "tile",
        "RS_PORT_TEST_TILE_URL",
        "http://localhost:8005",
        "Tile Service",
    ),
    (
        "AI gateway",
        "RS_PORT_TEST_AI_URL",
        "http://localhost:8006",
        "AI Gateway Service",
    ),
]


@pytest.mark.parametrize(
    ("service_name", "env_key", "default_url", "title_fragment"),
    SERVICE_PORTS,
)
def test_running_service_port_exposes_openapi_contract(
    service_name,
    env_key,
    default_url,
    title_fragment,
):
    base_url = os.getenv(env_key, default_url).rstrip("/")
    openapi_url = f"{base_url}/openapi.json"

    try:
        response = httpx.get(openapi_url, timeout=3.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.fail(f"{service_name} port check failed at {openapi_url}: {exc}")

    spec = response.json()
    assert title_fragment in spec["info"]["title"]
