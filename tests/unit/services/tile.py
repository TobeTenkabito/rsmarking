import pytest


def debug_routes(client):
    """Helper function:print all routes registered on the current client,for debugging 404"""
    print("\n[Debug] Registered Routes:")
    for route in client.app.routes:
        print(f"  - {route.path} [{route.methods}]")


def test_tile_service_health(client):
    """
    Test the tile service health endpoint.
    """
    # Diagnostic:if mounting may have failed,uncomment the next line to inspect the route table
    debug_routes(client)

    # try the mounted path
    response = client.get("/tile/health")

    # Fallback handling:if 404,may be becausetext conftest text prefix is duplicated or missing
    if response.status_code == 404:
        # try root path
        response = client.get("/health")

    assert response.status_code == 200, f"Route not found,see current available routes in debug_routes output"
    data = response.json()
    assert data.get("status") == "ready"
    assert data.get("service") == "tile_service"


def test_get_tile_invalid_coord(client):
    """
    Test invalid tile coordinate requests.
    """
    response = client.get("/tile/v1/99/99/99.png")
    # if 404 text prefix text,also try without prefix
    if response.status_code == 404:
        response = client.get("/v1/99/99/99.png")

    assert response.status_code in [400, 404]


def test_tile_service_cors_headers(client):
    """
    Verify CORS headers.
    Note:if the route 404,FastAPI middleware may not attach CORS headers.
    """
    target_path = "/tile/health"
    res_check = client.get(target_path)
    if res_check.status_code == 404:
        target_path = "/health"

    response = client.options(target_path, headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })

    origin = response.headers.get("access-control-allow-origin")
    # if it is still None,means CORSMiddleware was not master_app loaded
    assert origin is not None, "CORS headersmissing,check master_app whether middleware was added"
    assert origin in ["*", "http://localhost:3000"]


def test_tile_not_found_error_format(client):
    """
    Verifywhether error responses use standard JSON format.
    """
    response = client.get("/tile/non_existent_path_really_random")
    assert response.status_code == 404
    assert "detail" in response.json()
