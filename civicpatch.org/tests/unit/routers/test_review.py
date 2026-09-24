import asyncio
import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lib.auth import get_optional_user
from routers.api import review_actions as review_actions_router
from routers.api import review_cards as review_cards_router
from schemas.common import Identity, UserRole
from services.roster import CardSides

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    user_id="user-id-123",
)


def _user_at(role: UserRole) -> Identity:
    """Cookie-style identity at a specific trust level, for gate tests."""
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="sb-test",
        email="test@example.com",
        role=role.value,
        user_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )


def _client_as(identity: Identity) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: identity
    app.include_router(review_cards_router.get_router(None), prefix="/pull_requests")
    app.include_router(review_actions_router.get_router(None), prefix="/pull_requests")
    return TestClient(app)


TEST_CHANGESET_ID = "test-request-id-123"
TEST_PR_NUMBER = "42"
TEST_OCDID = "ocd-jurisdiction/country:us/state:ca/place:oakland/city"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(review_cards_router.get_router(None), prefix="/pull_requests")
    app.include_router(review_actions_router.get_router(None), prefix="/pull_requests")
    return TestClient(app)


@pytest.mark.unit
def test_list_pull_requests_returns_data(client):
    with patch(
        "database.review_pool.list_open_changesets",
        new_callable=AsyncMock,
        return_value=([], 0, 0),
    ):
        response = client.get(
            "/pull_requests",
            params={"jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.unit
def test_get_pull_requests_with_data_returns_paginated(client):
    with (
        patch(
            "database.review_pool.list_open_changesets",
            new_callable=AsyncMock,
            return_value=([], 0, 0),
        ),
    ):
        response = client.get("/pull_requests/with-data")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.unit
def test_get_pull_request_review_returns_the_summary(client):
    """Thin: the composition of stored and computed issues is the service's, tested there."""
    with patch(
        "routers.api.review_cards.review_summary_for_changeset",
        new_callable=AsyncMock,
        return_value={"issues": [{"code": "unverified_post"}]},
    ):
        response = client.get(f"/pull_requests/{TEST_CHANGESET_ID}/review")

    assert response.status_code == 200
    assert response.json()["data"]["issues"] == [{"code": "unverified_post"}]


@pytest.mark.unit
def test_rejecting_a_scrape_dismisses_it(client):
    with (
        patch(
            "database.users.get_user_id_by_provider",
            new_callable=AsyncMock,
            return_value="user-id-123",
        ),
        patch(
            "database.review_session_entries.resolve_entries_for_changeset",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "routers.api.review_actions.dismiss_people",
            new_callable=AsyncMock,
        ) as mock_dismiss,
    ):
        response = client.delete(
            f"/pull_requests/{TEST_CHANGESET_ID}",
            params={"changeset_id": TEST_CHANGESET_ID},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_resolve.assert_awaited_once_with(TEST_CHANGESET_ID)
    # Closing is the reviewer deciding not to publish, and that decision is now recorded
    # on the request rather than inferred from the PR's GitHub status.
    mock_dismiss.assert_awaited_once_with(TEST_CHANGESET_ID, "user-id-123")


@pytest.mark.unit
def test_publish_refuses_when_the_scrape_recorded_no_roster(client):
    """`data_json` is the only copy of the roster now. Publishing a request that never
    recorded one would resolve to [] and retire every person in the jurisdiction."""
    with (
        patch(
            "services.roster_edits.publish_roster", new_callable=AsyncMock
        ) as mock_publish,
        patch(
            "database.review_session_entries.resolve_entries_for_changeset",
            new_callable=AsyncMock,
        ),
        patch(
            "services.roster_edits.proposed_roster",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "services.roster_edits.scraped_roster",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/publish",
            json={"changeset_id": TEST_CHANGESET_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 409
    mock_publish.assert_not_awaited()


@pytest.mark.unit
def test_publish_returns_200_and_queues_no_merge(client):
    """Publishing settles within the request: the roster is written and the entry resolved
    before the response, so there is nothing for the caller to poll."""
    with (
        patch(
            "database.review_session_entries.resolve_entries_for_changeset",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "services.roster_edits.publish_roster", new_callable=AsyncMock
        ) as mock_publish,
        patch(
            "services.roster_edits.proposed_roster",
            new_callable=AsyncMock,
            return_value=[{**BASE_PERSON}],
        ),
        patch(
            "services.roster_edits.scraped_roster",
            new_callable=AsyncMock,
            return_value=[{**BASE_PERSON}],
        ),
    ):
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/publish",
            json={"changeset_id": TEST_CHANGESET_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    mock_resolve.assert_awaited_once_with(TEST_CHANGESET_ID)
    # No roster argument: publishing rebuilds from the facts, and the save filed them.
    mock_publish.assert_awaited_once_with(
        TEST_CHANGESET_ID, TEST_OCDID, "user-id-123", None
    )


# An Official-valid person in the scrape's stored roster, in on-disk field order. A patch
# overlays only the edited fields onto this base, so untouched fields and key order stay intact.
BASE_PERSON = {
    "name": "Jane Doe",
    "phones": ["(916) 808-5300"],
    "emails": [],
    "urls": [],
    "office": {"name": "Mayor", "division_ocdid": None},
    "jurisdiction_ocdid": TEST_OCDID,
    "source_urls": ["https://x.gov/council"],
    "updated_at": "2025-11-18T19:49:42+00:00",
    "id": "p1",
}


SAVE_PATCH = [{"id": "p1", "fields": {"phones": ["9165551234"]}}]


@pytest.mark.unit
def test_save_marks_the_entry_saved_without_publishing(client):
    """The whole point of /save: it marks the entry and triggers none of the merge machinery.

    This test verified that /save also wrote the reviewer's claims. It now verifies only the
    session bookkeeping, because the claims are filed by `POST /jurisdictions/roster-edits` before
    this call — one payload for the fields and the posts, one place that turns an answer into
    claims."""
    with (
        patch(
            "database.review_session_entries.save_entries_for_changeset",
            new_callable=AsyncMock,
        ) as mock_save,
        patch(
            "database.review_session_entries.resolve_entries_for_changeset",
            new_callable=AsyncMock,
        ) as mock_resolve,
    ):
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/save",
            json={
                "changeset_id": TEST_CHANGESET_ID,
                "jurisdiction_ocdid": TEST_OCDID,
                "data": SAVE_PATCH,
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    mock_save.assert_awaited_once_with(TEST_CHANGESET_ID)
    mock_resolve.assert_not_awaited()


@pytest.mark.unit
def test_save_requires_data(client):
    response = client.post(
        f"/pull_requests/{TEST_CHANGESET_ID}/save",
        json={"changeset_id": TEST_CHANGESET_ID, "jurisdiction_ocdid": TEST_OCDID},
    )
    assert response.status_code == 422


# ── get_pull_request_by_number tests ──────────────────────────────────────

OPEN_PR_DB_RESULT = {
    "changeset_id": TEST_CHANGESET_ID,
    "jurisdiction_ocdid": TEST_OCDID,
    "jurisdiction_name": "Oakland",
    "jurisdiction_website_url": "https://oaklandca.gov",
    "pr": {
        "url": "https://github.com/org/repo/pull/42",
        "status": "open",
        "number": 42,
    },
}

MERGED_PR_DB_RESULT = {
    **OPEN_PR_DB_RESULT,
    "pr": {
        "url": "https://github.com/org/repo/pull/42",
        "status": "merged",
        "number": 42,
    },
}


@pytest.mark.unit
def test_get_by_request_404_when_not_found(client):
    with patch(
        "database.review_pool.get_changeset_data",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get("/pull_requests/by-request/req-missing")

    assert response.status_code == 404


@pytest.mark.unit
def test_get_by_request_200_for_open_pr(client):
    with (
        patch(
            "database.review_pool.get_changeset_data",
            new_callable=AsyncMock,
            return_value=OPEN_PR_DB_RESULT,
        ),
        # Both sides of the card and the locks' disclosure, from one call: derived apart they
        # would take a `now()` each, and a claim landing between them would reach one side only.
        patch(
            "routers.api.review_cards.card_sides",
            new_callable=AsyncMock,
            return_value=CardSides([], [{"name": "Jane Doe"}], {}),
        ),
        patch(
            "database.jurisdictions.has_ever_collected",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = client.get(f"/pull_requests/by-request/{TEST_CHANGESET_ID}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["changeset_id"] == TEST_CHANGESET_ID
    assert data["pr"]["status"] == "open"
    assert data["has_next"] is False
    assert data["has_prev"] is False
    # never scraped → baseline mode
    assert data["mode"] == "baseline"


@pytest.mark.unit
def test_get_by_request_200_for_merged_pr(client):
    with (
        patch(
            "database.review_pool.get_changeset_data",
            new_callable=AsyncMock,
            return_value=MERGED_PR_DB_RESULT,
        ),
        # Both sides of the card and the locks' disclosure, from one call: derived apart they
        # would take a `now()` each, and a claim landing between them would reach one side only.
        patch(
            "routers.api.review_cards.card_sides",
            new_callable=AsyncMock,
            return_value=CardSides([], [{"name": "Jane Doe"}], {}),
        ),
        patch(
            "database.jurisdictions.has_ever_collected",
            new_callable=AsyncMock,
            return_value=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        ),
    ):
        response = client.get(f"/pull_requests/by-request/{TEST_CHANGESET_ID}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pr"]["status"] == "merged"
    # previously scraped → reconcile mode
    assert data["mode"] == "reconcile"


# ── do_merge unit tests ────────────────────────────────────────────────────

MERGE_KEY = f"merge_status:{TEST_PR_NUMBER}"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Auth gates on write routes ──────────────────────────────────────────────
#
# These routes require (TEAM_REQUIRED, UserRole.CONTRIBUTORS). The default-level
# (signed-in but no elevation) user must be rejected with 403; the auth-ladder
# cascade is proven separately in test_auth.py, so here we just pin the gate
# floor. save-and-merge is intentionally absent — reviewers (default role) may
# publish, so it is AUTHENTICATED; see test_save_and_merge_allows_default_role.


@pytest.mark.unit
@pytest.mark.parametrize(
    "method,url",
    [
        ("delete", f"/pull_requests/{TEST_PR_NUMBER}?changeset_id={TEST_CHANGESET_ID}"),
    ],
)
def test_pull_request_writes_reject_default_role(method, url):
    """Default-level users (just-signed-in, no elevation) must be 403'd from
    every write route that mutates PR state."""
    client = _client_as(_user_at(UserRole.DEFAULT))
    kwargs = {} if method == "delete" else {"json": {}}
    response = getattr(client, method)(url, **kwargs)
    assert response.status_code == 403


@pytest.mark.unit
def test_publish_allows_default_role():
    """A default-role reviewer may publish the scrape they're reviewing — the route is
    AUTHENTICATED, not contributor-gated."""
    client = _client_as(_user_at(UserRole.DEFAULT))
    with (
        patch(
            "database.review_session_entries.resolve_entries_for_changeset",
            new_callable=AsyncMock,
        ),
        patch("services.roster_edits.publish_roster", new_callable=AsyncMock),
        patch(
            "services.roster_edits.proposed_roster",
            new_callable=AsyncMock,
            return_value=[{**BASE_PERSON}],
        ),
        patch(
            "services.roster_edits.scraped_roster",
            new_callable=AsyncMock,
            return_value=[{**BASE_PERSON}],
        ),
    ):
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/publish",
            json={"changeset_id": TEST_CHANGESET_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 200


@pytest.mark.unit
def test_report_review_issue_allows_default_role():
    """A default-role reviewer may file a GitHub issue while reviewing — the
    route is AUTHENTICATED, not contributor-gated."""
    client = _client_as(_user_at(UserRole.DEFAULT))
    with patch(
        "services.review_issue_report.report_review_issue",
        new_callable=AsyncMock,
        return_value={
            "id": "issue-1",
            "github_issue_url": "https://github.com/org/open-data/issues/9",
            "github_issue_number": 9,
        },
    ) as mock_report:
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/issues",
            json={"description": "Something looks wrong."},
        )

    assert response.status_code == 200
    assert (
        response.json()["data"]["github_issue_url"]
        == "https://github.com/org/open-data/issues/9"
    )
    mock_report.assert_awaited_once()


@pytest.mark.unit
def test_report_review_issue_404_when_review_not_found(client):
    with patch(
        "services.review_issue_report.report_review_issue",
        new_callable=AsyncMock,
        side_effect=review_actions_router.review_issue_report_service.ReviewNotFoundError(
            "no review"
        ),
    ):
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/issues",
            json={"description": "Something looks wrong."},
        )

    assert response.status_code == 404


@pytest.mark.unit
def test_report_review_issue_502_when_github_fails(client):
    with patch(
        "services.review_issue_report.report_review_issue",
        new_callable=AsyncMock,
        side_effect=review_actions_router.review_issue_report_service.GithubIssueCreationError(
            "GitHub is down"
        ),
    ):
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/issues",
            json={"description": "Something looks wrong."},
        )

    assert response.status_code == 502


@pytest.mark.unit
def test_report_review_issue_422_on_empty_description(client):
    response = client.post(
        f"/pull_requests/{TEST_CHANGESET_ID}/issues",
        json={"description": ""},
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_report_review_issue_401_when_user_id_missing():
    identity = Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="sb-test",
        email="test@example.com",
        role=UserRole.DEFAULT.value,
        user_id=None,
    )
    client = _client_as(identity)
    response = client.post(
        f"/pull_requests/{TEST_CHANGESET_ID}/issues",
        json={"description": "Something looks wrong."},
    )

    assert response.status_code == 401


@pytest.mark.unit
def test_get_reported_issues_returns_data(client):
    with patch(
        "database.issues.get_user_reported_issues_for_changeset",
        new_callable=AsyncMock,
        return_value=[
            {
                "id": "issue-1",
                "github_issue_url": "https://github.com/org/open-data/issues/9",
                "github_issue_number": 9,
                "status": "pending",
            }
        ],
    ):
        response = client.get(f"/pull_requests/{TEST_CHANGESET_ID}/issues")

    assert response.status_code == 200
    assert response.json()["data"][0]["github_issue_number"] == 9


@pytest.mark.unit
def test_get_reported_issues_allows_default_role():
    """Reviewers (default role) can see issues they've already filed for this
    request — read-only, same gate as the POST that creates them."""
    client = _client_as(_user_at(UserRole.DEFAULT))
    with patch(
        "database.issues.get_user_reported_issues_for_changeset",
        new_callable=AsyncMock,
        return_value=[],
    ):
        response = client.get(f"/pull_requests/{TEST_CHANGESET_ID}/issues")

    assert response.status_code == 200


@pytest.mark.unit
def test_publishing_a_superseded_roster_is_a_409_not_a_500(client):
    """Two imports minutes apart leave two cards. Publishing the newer one makes the older
    stale, which is an expected state and has to read as one — it used to surface as a server
    error, which sends a reviewer hunting for a fault that is not there."""
    from database.publications import SupersededRoster

    with (
        patch(
            "database.review_session_entries.resolve_entries_for_changeset",
            new_callable=AsyncMock,
        ),
        patch(
            "routers.api.review_actions.roster_edits.publish",
            new_callable=AsyncMock,
            side_effect=SupersededRoster("A newer roster was already published"),
        ),
    ):
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/publish",
            json={"changeset_id": TEST_CHANGESET_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 409
    assert "newer roster" in response.json()["detail"]


@pytest.mark.unit
def test_a_sheet_import_publishes_from_its_review_card(client):
    """Out of the pool, so only its batch page's Edit link reaches this card — and publishing
    from there is the point of the link."""
    with (
        patch(
            "database.review_session_entries.resolve_entries_for_changeset",
            new_callable=AsyncMock,
        ),
        patch(
            "services.roster_edits.proposed_roster",
            new_callable=AsyncMock,
            return_value=[{"id": "p1", "name": "Ana Reyes"}],
        ),
        patch(
            "services.roster_edits.publish_roster", new_callable=AsyncMock
        ) as mock_publish,
    ):
        response = client.post(
            f"/pull_requests/{TEST_CHANGESET_ID}/publish",
            json={"changeset_id": TEST_CHANGESET_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 200
    mock_publish.assert_awaited_once()


@pytest.mark.unit
def test_publishing_a_selection_answers_per_card():
    client = _client_as(_user_at(UserRole.CONTRIBUTORS))
    with patch(
        "routers.api.review_actions.bulk_review_service.publish_selected",
        new_callable=AsyncMock,
        return_value=[],
    ) as publish:
        response = client.post(
            "/pull_requests/publish", json={"changeset_ids": [TEST_CHANGESET_ID]}
        )

    assert response.status_code == 200
    assert response.json() == {"data": []}
    publish.assert_awaited_once_with(
        [TEST_CHANGESET_ID], "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )


@pytest.mark.unit
def test_dismissing_a_selection_answers_with_what_was_dismissed():
    client = _client_as(_user_at(UserRole.CONTRIBUTORS))
    with patch(
        "routers.api.review_actions.bulk_review_service.dismiss_selected",
        new_callable=AsyncMock,
        return_value=[TEST_CHANGESET_ID],
    ):
        response = client.post(
            "/pull_requests/dismiss", json={"changeset_ids": [TEST_CHANGESET_ID]}
        )

    assert response.status_code == 200
    assert response.json() == {"data": [TEST_CHANGESET_ID]}


@pytest.mark.unit
@pytest.mark.parametrize("action", ["publish", "dismiss"])
def test_a_default_user_cannot_act_on_a_selection(action):
    """The Queue is contributor-level; publishing one card you are reviewing is not."""
    client = _client_as(_user_at(UserRole.DEFAULT))
    response = client.post(
        f"/pull_requests/{action}", json={"changeset_ids": [TEST_CHANGESET_ID]}
    )
    assert response.status_code in (401, 403)


@pytest.mark.unit
def test_cards_are_loaded_for_the_ids_asked_for(client):
    with patch(
        "routers.api.review_cards.review_cards_service.with_card_data",
        new_callable=AsyncMock,
        return_value=[],
    ) as load:
        response = client.get(
            "/pull_requests/cards",
            params=[("changeset_ids", "a"), ("changeset_ids", "b")],
        )

    assert response.status_code == 200
    assert response.json() == {"data": []}
    load.assert_awaited_once_with(["a", "b"])
