from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.coverage import Bucket, StateCoverage
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

MOCK_MUNICIPALITY_LIST = [
    {
        "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:co/place:denver/government",
        "name": "Denver",
        "status": "fresh",
        "officials_count": 12,
        "last_verified_at": "2026-04-01T00:00:00+00:00",
        "needs_review": False,
    },
]


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


@pytest.mark.unit
def test_get_state_summary_returns_coverage(client):
    cov = StateCoverage(
        total=10,
        scrapeable=8,
        covered_fresh=5,
        covered_stale=2,
        buckets={b: 0 for b in Bucket},
        needs_review_count=1,
    )
    with patch(
        "services.coverage.get_state_coverage",
        new_callable=AsyncMock,
        return_value=cov,
    ):
        response = client.get("/coverage/wa/summary")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["covered_fresh"] == 5
    assert data["covered"] == 7  # computed field serializes
    assert data["reach_fraction"] == pytest.approx(7 / 8)  # computed field serializes


@pytest.mark.unit
def test_get_municipalities_returns_service_data(client):
    with patch(
        "services.coverage.get_municipality_list",
        new_callable=AsyncMock,
        return_value=MOCK_MUNICIPALITY_LIST,
    ):
        response = client.get("/coverage/co/municipalities")

    assert response.status_code == 200
    assert response.json() == {"data": MOCK_MUNICIPALITY_LIST}
