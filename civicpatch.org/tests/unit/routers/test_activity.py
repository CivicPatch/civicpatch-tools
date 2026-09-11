from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lib.auth import get_optional_user
from schemas.common import Identity, UserRole

from routers.api import activity as change_logs_router

_IDENTITY = Identity(
    type="cookie",
    provider="supabase",
    provider_user_id="user-uuid",
    email="user@example.com",
    role=UserRole.DEFAULT.value,
)

PUBLICATION_ROW = {
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:wa/place:seattle/government",
    "jurisdiction_name": "Seattle city",
    "state": "wa",
    "commit_url": "https://github.com/org/open-data/commit/abc123",
    "kind": "scrape",
    "created_at": "2026-05-24T13:27:00+00:00",
    "review_count": 1,
}

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
    "is_system": False,
    "jurisdiction_name": "Seattle city",
    "pull_request_url": "https://github.com/org/repo/pull/42",
    "summary": "Edited Jane Doe (1 field)",
}


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: _IDENTITY
    app.include_router(change_logs_router.get_router(), prefix="/change_logs")
    return TestClient(app)


@pytest.fixture
def anonymous_client() -> TestClient:
    app = FastAPI()
    app.include_router(change_logs_router.get_router(), prefix="/change_logs")
    return TestClient(app)


@pytest.mark.unit
def test_quarantined_queries_default_role(client):
    # Every signed-in user may see quarantined changes — the router mount already requires
    # that, so there is no further role check here.
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs", params={"authors": "quarantined"})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(["default"], 20, 0)


@pytest.mark.unit
def test_all_applies_no_role_filter(client):
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(None, 20, 0)


@pytest.mark.unit
def test_all_is_the_default_filter(client):
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(0, [])) as mock_get:
        response = client.get("/change_logs")

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(None, 20, 0)


@pytest.mark.unit
def test_pagination_offset_computed_from_page(client):
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(45, [])) as mock_get:
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
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.status_code == 200
    entry = response.json()["data"][0]
    assert entry["author_role"] == "admins"
    assert entry["jurisdiction_name"] == "Seattle city"
    assert entry["changes"]["fields"][0] == {"field": "name", "before": "Jane", "after": "Jane Doe"}


@pytest.mark.unit
def test_system_actor_is_flagged(client):
    row = {**ROW, "author_name": "CivicPatch", "is_system": True}
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(1, [row])):
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.json()["data"][0]["is_system"] is True


@pytest.mark.unit
def test_pull_request_url_maps_to_entry(client):
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.json()["data"][0]["pull_request_url"] == "https://github.com/org/repo/pull/42"


@pytest.mark.unit
def test_pull_request_url_null_when_no_pr(client):
    row = {**ROW, "pull_request_url": None}
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(1, [row])):
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
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(1, [ROW])):
        response = client.get("/change_logs", params={"authors": "all"})

    entry = response.json()["data"][0]
    assert entry["jurisdiction_path"] == ROW["jurisdiction_ocdid"]


@pytest.mark.unit
def test_jurisdiction_path_null_when_no_ocdid(client):
    row = {**ROW, "jurisdiction_ocdid": None}
    with patch("database.activity.get_activity_for_roles", new_callable=AsyncMock, return_value=(1, [row])):
        response = client.get("/change_logs", params={"authors": "all"})

    assert response.json()["data"][0]["jurisdiction_path"] is None


@pytest.mark.unit
def test_activity_endpoint_rejects_anonymous_visitor(anonymous_client):
    response = anonymous_client.get("/change_logs")
    assert response.status_code == 403


# ── GET /change_logs/recent-publications (public) ──────────────────────


@pytest.mark.unit
def test_recent_publications_is_open_to_an_anonymous_visitor(anonymous_client):
    with patch(
        "database.activity.get_recent_publications",
        new_callable=AsyncMock,
        return_value=[PUBLICATION_ROW],
    ):
        response = anonymous_client.get("/change_logs/recent-publications")

    assert response.status_code == 200
    entry = response.json()["data"][0]
    assert entry["jurisdiction_name"] == "Seattle city"
    assert entry["commit_url"] == "https://github.com/org/open-data/commit/abc123"


@pytest.mark.unit
def test_recent_publications_carries_no_review_detail(anonymous_client):
    """The public feed must never leak the raw diff or the internal summary text — only
    the fields `PublicPublication` declares reach the response."""
    with patch(
        "database.activity.get_recent_publications",
        new_callable=AsyncMock,
        return_value=[PUBLICATION_ROW],
    ):
        response = anonymous_client.get("/change_logs/recent-publications")

    entry = response.json()["data"][0]
    assert "changes" not in entry
    assert "summary" not in entry


@pytest.mark.unit
def test_recent_publications_carries_no_author_info(anonymous_client):
    """The public feed says which jurisdiction changed, not who changed it — even if the
    DB layer's row happened to carry author fields, PublicPublication doesn't declare them,
    so they must never reach the response."""
    row = {**PUBLICATION_ROW, "author_name": "michelle@civicpatch.org", "author_role": "admins"}
    with patch(
        "database.activity.get_recent_publications",
        new_callable=AsyncMock,
        return_value=[row],
    ):
        response = anonymous_client.get("/change_logs/recent-publications")

    entry = response.json()["data"][0]
    assert "author_name" not in entry
    assert "author_role" not in entry


@pytest.mark.unit
def test_recent_publications_uses_the_requested_limit(anonymous_client):
    with patch(
        "database.activity.get_recent_publications", new_callable=AsyncMock, return_value=[]
    ) as mock_get:
        anonymous_client.get("/change_logs/recent-publications", params={"limit": 5})

    mock_get.assert_awaited_once_with(5)


@pytest.mark.unit
def test_recent_publications_defaults_to_a_small_limit(anonymous_client):
    with patch(
        "database.activity.get_recent_publications", new_callable=AsyncMock, return_value=[]
    ) as mock_get:
        anonymous_client.get("/change_logs/recent-publications")

    mock_get.assert_awaited_once_with(10)


@pytest.mark.unit
def test_recent_publications_carries_a_review_count(anonymous_client):
    """Grouping happens in the DB query — the router just has to carry the count through
    rather than dropping it, so a heavily-reviewed town says so instead of looking like
    one town filled several of the feed's slots."""
    row = {**PUBLICATION_ROW, "review_count": 3}
    with patch(
        "database.activity.get_recent_publications",
        new_callable=AsyncMock,
        return_value=[row],
    ):
        response = anonymous_client.get("/change_logs/recent-publications")

    assert response.json()["data"][0]["review_count"] == 3
