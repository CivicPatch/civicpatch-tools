"""Tests for admin router endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from src.routers.api.admin import get_router
from src.schemas.requests import OdSyncRequestSchema


@pytest.fixture
def client():
    """Create a test client for the admin router."""
    from fastapi import FastAPI
    app = FastAPI()
    router = get_router()
    app.include_router(router)
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
