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
def test_dashboard_returns_cached(client):
    with patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=MOCK_DASHBOARD):
        response = client.get("/data/dashboard")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_DASHBOARD}


@pytest.mark.unit
def test_dashboard_fetches_from_db_on_cache_miss(client):
    mock_set_cached = AsyncMock()
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch("database.dashboard.get_dashboard", new_callable=AsyncMock, return_value=MOCK_DASHBOARD),
        patch("lib.cache.set_cached", mock_set_cached),
    ):
        response = client.get("/data/dashboard")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_DASHBOARD}
    mock_set_cached.assert_called_once()
    assert mock_set_cached.call_args[0][0] == "dashboard_data"
    assert mock_set_cached.call_args[0][1] == MOCK_DASHBOARD


@pytest.mark.unit
def test_dashboard_does_not_cache_empty_db_result(client):
    """Regression guard: caching an empty result would poison the cache for 1 day."""
    mock_set_cached = AsyncMock()
    empty = {"states": {}}
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch("database.dashboard.get_dashboard", new_callable=AsyncMock, return_value=empty),
        patch("lib.cache.set_cached", mock_set_cached),
    ):
        response = client.get("/data/dashboard")

    assert response.status_code == 200
    assert response.json() == {"data": empty}
    mock_set_cached.assert_not_called()
