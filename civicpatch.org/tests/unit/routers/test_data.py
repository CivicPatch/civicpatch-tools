import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from routers.api import data as data_router


MOCK_DASHBOARD = {
    "states": {
        "co": {
            "state": "co",
            "civicpatch": {
                "officials": 850,
                "localities": {"known": 271, "scrapeable": 250, "coverage": 120},
            },
        }
    }
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(data_router.get_router(), prefix="/data")
    return TestClient(app)


@pytest.mark.unit
def test_dashboard_returns_db_data(client):
    # Computed live, no cache (the coverage-presentation plan dropped the 1-day cache).
    with patch(
        "database.dashboard.get_dashboard",
        new_callable=AsyncMock,
        return_value=MOCK_DASHBOARD,
    ):
        response = client.get("/data/dashboard")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_DASHBOARD}
