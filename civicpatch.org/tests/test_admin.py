"""Tests for admin router endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from lib.auth import get_optional_user
from src.routers.api.admin import get_router
from src.schemas.common import Identity
from src.schemas.open_data import OdSyncRequestSchema

# service_api_key identities bypass the route role check, so this satisfies the admin guard.
MOCK_ADMIN = Identity(type="service_api_key", provider="service", provider_user_id="svc", email=None)


@pytest.fixture
def client():
    """Create a test client for the admin router."""
    from fastapi import FastAPI
    app = FastAPI()
    router = get_router()
    app.include_router(router)
    app.dependency_overrides[get_optional_user] = lambda: MOCK_ADMIN
    return TestClient(app)

@pytest.mark.unit
def test_od_sync_request_schema_validation():
    """Test OdSyncRequestSchema validation."""
    # Valid schema
    valid_data = {
        "jurisdiction_ocdids": ["ocd-division/country:us/state:ca"],
        "force": False
    }
    schema = OdSyncRequestSchema(**valid_data)
    assert schema.jurisdiction_ocdids == ["ocd-division/country:us/state:ca"]
    
    # Test with force=True
    valid_data_with_force = {
        "jurisdiction_ocdids": ["ocd-division/country:us/state:ny"],
        "force": True
    }
    schema = OdSyncRequestSchema(**valid_data_with_force)


@pytest.mark.unit
def test_od_sync_no_ocdids_triggers_full_sync(client):
    with (
        patch("src.routers.api.admin.temporal_client.trigger_full_od_sync", new_callable=AsyncMock) as mock_full,
        patch("src.routers.api.admin.temporal_client.start_targeted_od_sync", new_callable=AsyncMock) as mock_targeted,
    ):
        response = client.post("/od_sync", json={})

    assert response.status_code == 200
    mock_full.assert_awaited_once()
    mock_targeted.assert_not_awaited()


@pytest.mark.unit
def test_od_sync_with_ocdids_starts_targeted_workflow(client):
    ocdids = ["ocd-division/country:us/state:ca"]
    with (
        patch("src.routers.api.admin.temporal_client.trigger_full_od_sync", new_callable=AsyncMock) as mock_full,
        patch("src.routers.api.admin.temporal_client.start_targeted_od_sync", new_callable=AsyncMock) as mock_targeted,
    ):
        response = client.post("/od_sync", json={"jurisdiction_ocdids": ocdids})

    assert response.status_code == 200
    mock_targeted.assert_awaited_once_with(ocdids)
    mock_full.assert_not_awaited()
