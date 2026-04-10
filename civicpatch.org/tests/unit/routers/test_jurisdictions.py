import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from routers.api import jurisdictions as jurisdictions_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jurisdictions_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


@pytest.mark.unit
def test_get_jurisdiction_states_returns_list(client):
    mock_states = [{"code": "ca", "name": "California"}, {"code": "ny", "name": "New York"}]
    with patch(
        "shared.utils.config_utils.get_states",
        return_value=mock_states,
    ):
        response = client.get("/jurisdictions/states")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total_items" in data
    assert data["total_items"] == 2


@pytest.mark.unit
def test_get_jurisdictions_by_ocdids_returns_data(client):
    with patch(
        "database.database.get_jurisdictions_by_ocdids",
        new_callable=AsyncMock,
        return_value=[{"id": "ocd-jurisdiction/country:us/state:ca/place:oakland", "name": "Oakland"}],
    ):
        response = client.post(
            "/jurisdictions/by-ocdids",
            json={"ocdids": ["ocd-jurisdiction/country:us/state:ca/place:oakland"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.unit
def test_get_jurisdiction_history_returns_data(client):
    with patch(
        "database.database.get_jurisdiction_history",
        new_callable=AsyncMock,
        return_value=[{"request_id": "req-1", "status": "complete"}],
    ):
        response = client.get(
            "/jurisdictions/history",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.unit
def test_get_jurisdiction_history_returns_404_when_none(client):
    with patch(
        "database.database.get_jurisdiction_history",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(
            "/jurisdictions/history",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:unknown"},
        )

    assert response.status_code == 404


@pytest.mark.unit
def test_get_jurisdiction_returns_data(client):
    with patch(
        "database.database.get_jurisdiction",
        new_callable=AsyncMock,
        return_value={"data": {"id": "ocd-jurisdiction/country:us/state:ca/place:oakland", "name": "Oakland"}, "geo_center": None},
    ):
        response = client.get(
            "/jurisdictions",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.unit
def test_get_jurisdiction_returns_404_when_not_found(client):
    with patch(
        "database.database.get_jurisdiction",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(
            "/jurisdictions",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:unknown"},
        )

    assert response.status_code == 404
