from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api import change_logs as change_logs_router

ROW = {
    "id": "cl-1",
    "type": "edit_person",
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:wa/place:seattle/government",
    "changeset_id": "req-1",
    "changes": {
        "person_id": "p1",
        "person_name": "Jane Doe",
        "fields": [{"field": "name", "before": "Jane", "after": "Jane Doe"}],
    },
    "created_at": "2026-05-24T13:27:00+00:00",
    "author_name": "michelle@civicpatch.org",
    "author_role": "admins",
    "jurisdiction_name": "Seattle city",
    "pull_request_url": "https://github.com/org/repo/pull/42",
    "summary": "Edited Jane Doe (1 field)",
}


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(change_logs_router.get_router(), prefix="/change_logs")
    return TestClient(app)


@pytest.mark.unit
def test_quarantined_queries_default_role(client):
    # Every signed-in user may see quarantined changes — the router mount already requires
    # that, so there is no further role check here.
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs", params={"authors": "quarantined"})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(["default"], 20, 0)


@pytest.mark.unit
def test_all_applies_no_role_filter(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(None, 20, 0)


@pytest.mark.unit
def test_all_is_the_default_filter(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs")

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(None, 20, 0)


@pytest.mark.unit
def test_pagination_offset_computed_from_page(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(45, [])) as mock_get:
        response = client.get("/change_logs", params={"authors": "all", "page": 3, "per_page": 10})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(None, 10, 20)
    body = response.json()
    assert body["total_items"] == 45
    assert body["page"] == 3
    assert body["total_pages"] == 5


@pytest.mark.unit
def test_unknown_authors_filter_rejected(client):
    response = client.get("/change_logs", params={"authors": "everything"})
    assert response.status_code == 422


@pytest.mark.unit
def test_row_maps_to_entry(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.status_code == 200
    entry = response.json()["data"][0]
    assert entry["author_role"] == "admins"
    assert entry["jurisdiction_name"] == "Seattle city"
    assert entry["changes"]["fields"][0] == {"field": "name", "before": "Jane", "after": "Jane Doe"}


@pytest.mark.unit
def test_pull_request_url_maps_to_entry(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.json()["data"][0]["pull_request_url"] == "https://github.com/org/repo/pull/42"


@pytest.mark.unit
def test_pull_request_url_null_when_no_pr(client):
    row = {**ROW, "pull_request_url": None}
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [row])):
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.json()["data"][0]["pull_request_url"] is None


@pytest.mark.unit
def test_jurisdiction_path_is_the_ocdid(client):
    """A jurisdiction page's URL is its ocdid.

    This asserted `jurisdiction_ocdid_to_folder(ocdid)`, which was true while the URL was the
    `{state}/local/{place}` folder form. That encoding is now only the open-data repo's
    directory layout — deriving a URL from it meant two encoders, one Python and one
    JavaScript, that had to agree.
    """
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"authors": "all"})

    entry = response.json()["data"][0]
    assert entry["jurisdiction_path"] == ROW["jurisdiction_ocdid"]


@pytest.mark.unit
def test_jurisdiction_path_null_when_no_ocdid(client):
    row = {**ROW, "jurisdiction_ocdid": None}
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [row])):
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.json()["data"][0]["jurisdiction_path"] is None
