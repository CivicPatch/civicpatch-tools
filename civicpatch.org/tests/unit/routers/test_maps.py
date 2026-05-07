import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, Role
from lib.auth import get_optional_user
from routers.api import maps as maps_router

MOCK_ADMIN = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    teams=[Role.CONTRIBUTORS, Role.MAINTAINERS, Role.ADMINS, Role.DEFAULT],
)

@pytest.fixture
def admin_client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_ADMIN
    app.include_router(maps_router.get_router(), prefix="/maps")
    return TestClient(app)


@pytest.mark.unit
def test_sync_all_states(admin_client):
    with patch(
        "routers.api.maps.map_client.start_sync_jurisdiction_map_workflow",
        new_callable=AsyncMock,
        return_value="sync-jurisdiction-map-all",
    ) as mock_start:
        response = admin_client.post("/maps/sync")

    assert response.status_code == 200
    assert response.json() == {"workflow_id": "sync-jurisdiction-map-all", "state": None}
    mock_start.assert_called_once_with(None)


@pytest.mark.unit
def test_sync_single_state(admin_client):
    with patch(
        "routers.api.maps.map_client.start_sync_jurisdiction_map_workflow",
        new_callable=AsyncMock,
        return_value="sync-jurisdiction-map-co",
    ) as mock_start:
        response = admin_client.post("/maps/sync", json={"state": "co"})

    assert response.status_code == 200
    assert response.json()["state"] == "co"
    mock_start.assert_called_once_with("co")


@pytest.mark.unit
def test_sync_invalid_state_returns_422(admin_client):
    with patch(
        "routers.api.maps.map_client.start_sync_jurisdiction_map_workflow",
        new_callable=AsyncMock,
    ):
        response = admin_client.post("/maps/sync", json={"state": "zzz"})

    assert response.status_code == 422


