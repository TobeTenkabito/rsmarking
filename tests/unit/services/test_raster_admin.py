from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.data_service.database import get_db
from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.routers.raster_router import router

ENDPOINT = "/admin/rasters/clear"
CONFIRM = {"confirmation": "DELETE_ALL_RASTERS"}


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.delenv("RS_ENABLE_ADMIN_OPERATIONS", raising=False)
    monkeypatch.delenv("RS_ADMIN_TOKEN", raising=False)
    clear = AsyncMock(return_value=True)
    monkeypatch.setattr(RasterCRUD, "clear_all_rasters", clear)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: object()
    with TestClient(app) as client:
        yield client, clear


def test_destructive_get_endpoint_removed(admin_client):
    client, clear = admin_client
    assert client.get("/debug/clear-db").status_code == 404
    assert client.get(ENDPOINT).status_code == 405
    clear.assert_not_awaited()


def test_admin_operations_disabled_by_default(admin_client, monkeypatch):
    client, clear = admin_client
    monkeypatch.setenv("RS_ADMIN_TOKEN", "correct-token")
    assert client.post(ENDPOINT, json=CONFIRM, headers={"Authorization": "Bearer correct-token"}).status_code == 404
    clear.assert_not_awaited()


def test_enable_without_token_fails_closed(admin_client, monkeypatch):
    client, clear = admin_client
    monkeypatch.setenv("RS_ENABLE_ADMIN_OPERATIONS", "true")
    assert client.post(ENDPOINT, json=CONFIRM).status_code == 503
    clear.assert_not_awaited()


@pytest.mark.parametrize("auth", [None, "Bearer wrong-token", "Basic correct-token", "Bearer 非ASCII"])
def test_enabled_requires_valid_bearer_token(admin_client, monkeypatch, auth):
    client, clear = admin_client
    monkeypatch.setenv("RS_ENABLE_ADMIN_OPERATIONS", "true")
    monkeypatch.setenv("RS_ADMIN_TOKEN", "correct-token")
    headers = {"Authorization": auth.encode("utf-8")} if auth else {}
    response = client.post(ENDPOINT, json=CONFIRM, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    clear.assert_not_awaited()


def test_valid_token_still_requires_explicit_confirmation(admin_client, monkeypatch):
    client, clear = admin_client
    monkeypatch.setenv("RS_ENABLE_ADMIN_OPERATIONS", "true")
    monkeypatch.setenv("RS_ADMIN_TOKEN", "correct-token")
    response = client.post(ENDPOINT, json={"confirmation": "yes"}, headers={"Authorization": "Bearer correct-token"})
    assert response.status_code == 422
    clear.assert_not_awaited()


def test_valid_admin_post_clears_rasters(admin_client, monkeypatch):
    client, clear = admin_client
    monkeypatch.setenv("RS_ENABLE_ADMIN_OPERATIONS", "true")
    monkeypatch.setenv("RS_ADMIN_TOKEN", "correct-token")
    response = client.post(ENDPOINT, json=CONFIRM, headers={"Authorization": "Bearer correct-token"})
    assert response.status_code == 200
    clear.assert_awaited_once()
