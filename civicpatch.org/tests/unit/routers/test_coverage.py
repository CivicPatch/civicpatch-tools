from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers.api import coverage as coverage_router

MOCK_COVERAGE = {
    "co": {
        "state": {
            "ocdid": "ocd-jurisdiction/country:us/state:co/government",
            "total": 271,
            "covered": 120,
        },
        "counties": {
            "ocd-jurisdiction/country:us/state:co/county:adams/government": {
                "total": 6,
                "covered": 5,
            }
        },
    },
}

MOCK_LOCAL_STATUS = {
    "ocd-jurisdiction/country:us/state:co/place:denver/government": "fresh",
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(coverage_router.get_router(), prefix="/coverage")
    return TestClient(app)


@pytest.mark.unit
def test_get_maps_coverage_returns_db_data(client):
    # Computed live, no cache (the coverage-presentation plan dropped the 1-hour cache).
    with patch(
        "database.coverage.get_maps_coverage",
        new_callable=AsyncMock,
        return_value=MOCK_COVERAGE,
    ):
        response = client.get("/coverage")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_COVERAGE}


@pytest.mark.unit
def test_get_local_status_returns_db_data(client):
    with patch(
        "database.coverage.get_local_status_for_state",
        new_callable=AsyncMock,
        return_value=MOCK_LOCAL_STATUS,
    ):
        response = client.get("/coverage/co/local")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_LOCAL_STATUS}
