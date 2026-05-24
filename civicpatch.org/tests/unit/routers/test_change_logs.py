from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api import change_logs as change_logs_router

ROW = {
    "id": "cl-1",
    "type": "edit_person",
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:wa/place:seattle/government",
    "request_id": "req-1",
    "changes": {
        "person_id": "p1",
        "person_name": "Jane Doe",
        "fields": [{"field": "name", "from": "Jane", "to": "Jane Doe"}],
    },
    "created_at": "2026-05-24T13:27:00+00:00",
    "author_name": "michelle@civicpatch.org",
    "author_role": "admins",
    "jurisdiction_name": "Seattle city",
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(change_logs_router.get_router(), prefix="/change_logs")
    return TestClient(app)


@pytest.mark.unit
def test_quarantine_bucket_queries_default_role(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs", params={"bucket": "quarantine"})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(["default"], 20, 0)


@pytest.mark.unit
def test_activity_bucket_queries_trusted_roles(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs", params={"bucket": "activity"})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(["contributors", "maintainers", "admins"], 20, 0)


@pytest.mark.unit
def test_pagination_offset_computed_from_page(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(45, [])) as mock_get:
        response = client.get("/change_logs", params={"bucket": "activity", "page": 3, "per_page": 10})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(["contributors", "maintainers", "admins"], 10, 20)
    body = response.json()
    assert body["total_items"] == 45
    assert body["page"] == 3
    assert body["total_pages"] == 5


@pytest.mark.unit
def test_unknown_bucket_rejected(client):
    response = client.get("/change_logs", params={"bucket": "everything"})
    assert response.status_code == 422


@pytest.mark.unit
def test_row_maps_to_entry_preserving_from_key(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"bucket": "activity"})

    assert response.status_code == 200
    entry = response.json()["data"][0]
    assert entry["author_role"] == "admins"
    assert entry["jurisdiction_name"] == "Seattle city"
    assert entry["changes"]["fields"][0] == {"field": "name", "from": "Jane", "to": "Jane Doe"}
