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
            "scraped": 120,
        },
        "counties": {
            "ocd-jurisdiction/country:us/state:co/county:adams/government": {
                "total": 6,
                "scraped": 5,
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
def test_get_maps_coverage_returns_cached(client):
    with patch(
        "lib.cache.get_cached", new_callable=AsyncMock, return_value=MOCK_COVERAGE
    ):
        response = client.get("/coverage")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_COVERAGE}


@pytest.mark.unit
def test_get_maps_coverage_fetches_from_db_on_cache_miss(client):
    mock_set_cached = AsyncMock()
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch(
            "database.coverage.get_maps_coverage",
            new_callable=AsyncMock,
            return_value=MOCK_COVERAGE,
        ),
        patch("lib.cache.set_cached", mock_set_cached),
    ):
        response = client.get("/coverage")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_COVERAGE}
    mock_set_cached.assert_called_once()
    assert mock_set_cached.call_args[0][0] == "coverage"
    assert mock_set_cached.call_args[0][1] == MOCK_COVERAGE


@pytest.mark.unit
def test_get_maps_coverage_does_not_cache_empty_db_result(client):
    """Regression: an empty DB result was being cached and poisoning the cache for 1h,
    making the map render all-red on fresh-DB setups."""
    mock_set_cached = AsyncMock()
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch(
            "database.coverage.get_maps_coverage",
            new_callable=AsyncMock,
            return_value={},
        ),
        patch("lib.cache.set_cached", mock_set_cached),
    ):
        response = client.get("/coverage")

    assert response.status_code == 200
    assert response.json() == {"data": {}}
    mock_set_cached.assert_not_called()


@pytest.mark.unit
def test_get_local_status_returns_cached(client):
    with patch(
        "lib.cache.get_cached", new_callable=AsyncMock, return_value=MOCK_LOCAL_STATUS
    ):
        response = client.get("/coverage/co/local")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_LOCAL_STATUS}


@pytest.mark.unit
def test_get_local_status_does_not_cache_empty_db_result(client):
    mock_set_cached = AsyncMock()
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch(
            "database.coverage.get_local_status_for_state",
            new_callable=AsyncMock,
            return_value={},
        ),
        patch("lib.cache.set_cached", mock_set_cached),
    ):
        response = client.get("/coverage/co/local")

    assert response.status_code == 200
    assert response.json() == {"data": {}}
    mock_set_cached.assert_not_called()
