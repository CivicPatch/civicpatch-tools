from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import change_logs as change_logs_router
from schemas.common import Identity, UserRole


def _identity(role: str | None) -> Identity | None:
    if role is None:
        return None
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="sb-1",
        email="user@example.com",
        role=role,
        user_id="11111111-1111-1111-1111-111111111111",
    )

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


def _client(role: str | None = UserRole.MAINTAINERS.value) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: _identity(role)
    app.include_router(change_logs_router.get_router(), prefix="/change_logs")
    return TestClient(app)


@pytest.fixture
def client():
    return _client()


@pytest.mark.unit
def test_quarantine_bucket_queries_default_role(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs", params={"bucket": "quarantine"})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(["default"], 20, 0)


@pytest.mark.unit
def test_quarantine_bucket_forbidden_for_default_role():
    client = _client(role=UserRole.DEFAULT.value)
    response = client.get("/change_logs", params={"bucket": "quarantine"})
    assert response.status_code == 403


@pytest.mark.unit
def test_quarantine_bucket_forbidden_for_contributors():
    client = _client(role=UserRole.CONTRIBUTORS.value)
    response = client.get("/change_logs", params={"bucket": "quarantine"})
    assert response.status_code == 403


@pytest.mark.unit
def test_quarantine_bucket_allowed_for_admins():
    client = _client(role=UserRole.ADMINS.value)
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])):
        response = client.get("/change_logs", params={"bucket": "quarantine"})
    assert response.status_code == 200


@pytest.mark.unit
def test_activity_bucket_queries_trusted_roles(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs", params={"bucket": "activity"})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(["contributors", "maintainers", "admins"], 20, 0)


@pytest.mark.unit
def test_activity_bucket_allowed_for_default_role():
    # The trusted-author change log is visible to any signed-in user.
    client = _client(role=UserRole.DEFAULT.value)
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(0, [])):
        response = client.get("/change_logs", params={"bucket": "activity"})
    assert response.status_code == 200


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
def test_row_maps_to_entry(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"bucket": "activity"})

    assert response.status_code == 200
    entry = response.json()["data"][0]
    assert entry["author_role"] == "admins"
    assert entry["jurisdiction_name"] == "Seattle city"
    assert entry["changes"]["fields"][0] == {"field": "name", "before": "Jane", "after": "Jane Doe"}


@pytest.mark.unit
def test_pull_request_url_maps_to_entry(client):
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"bucket": "activity"})

    assert response.json()["data"][0]["pull_request_url"] == "https://github.com/org/repo/pull/42"


@pytest.mark.unit
def test_pull_request_url_null_when_no_pr(client):
    row = {**ROW, "pull_request_url": None}
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [row])):
        response = client.get("/change_logs", params={"bucket": "activity"})

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
        response = client.get("/change_logs", params={"bucket": "activity"})

    entry = response.json()["data"][0]
    assert entry["jurisdiction_path"] == ROW["jurisdiction_ocdid"]


@pytest.mark.unit
def test_jurisdiction_path_null_when_no_ocdid(client):
    row = {**ROW, "jurisdiction_ocdid": None}
    with patch("database.change_logs.get_change_logs_for_roles", new_callable=AsyncMock, return_value=(1, [row])):
        response = client.get("/change_logs", params={"bucket": "activity"})

    assert response.json()["data"][0]["jurisdiction_path"] is None
