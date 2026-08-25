import asyncio
import datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, UserRole
from lib.auth import get_optional_user
from routers.api import pull_requests as pull_requests_router

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
    app.include_router(pull_requests_router.get_router(None), prefix="/pull_requests")
    return TestClient(app)

TEST_REQUEST_ID = "test-request-id-123"
TEST_PR_NUMBER = "42"
TEST_OCDID = "ocd-jurisdiction/country:us/state:ca/place:oakland/city"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(pull_requests_router.get_router(None), prefix="/pull_requests")
    return TestClient(app)


@pytest.mark.unit
def test_list_pull_requests_returns_data(client):
    with patch(
        "database.pull_requests.list_open_pull_requests",
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
            "database.pull_requests.list_open_pull_requests",
            new_callable=AsyncMock,
            return_value=([], 0, 0),
        ),
        patch(
            "database.people.get_people_by_jurisdictions",
            new_callable=AsyncMock,
            return_value={},
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
        "routers.api.pull_requests.review_summary_for_request",
        new_callable=AsyncMock,
        return_value={"issues": [{"code": "unverified_post"}]},
    ):
        response = client.get(f"/pull_requests/{TEST_REQUEST_ID}/review")

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
            "services.change_logs.record_close",
            new_callable=AsyncMock,
        ),
        patch(
            "database.review_session_entries.resolve_entries_for_request",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "routers.api.pull_requests.dismiss_people",
            new_callable=AsyncMock,
        ) as mock_dismiss,
    ):
        response = client.delete(
            f"/pull_requests/{TEST_REQUEST_ID}",
            params={"request_id": TEST_REQUEST_ID},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_resolve.assert_awaited_once_with(TEST_REQUEST_ID)
    # Closing is the reviewer deciding not to publish, and that decision is now recorded
    # on the request rather than inferred from the PR's GitHub status.
    mock_dismiss.assert_awaited_once_with(TEST_REQUEST_ID, "user-id-123")


@pytest.mark.unit
def test_publish_refuses_when_the_scrape_recorded_no_roster(client):
    """`data_json` is the only copy of the roster now. Publishing a request that never
    recorded one would resolve to [] and retire every person in the jurisdiction."""
    with (
        patch("services.roster_edits.publish_people", new_callable=AsyncMock) as mock_publish,
        patch("services.roster_edits.promote_to_reviewed", new_callable=AsyncMock),
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock),
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[]),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/publish",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 409
    mock_publish.assert_not_awaited()


@pytest.mark.unit
def test_save_refuses_when_the_scrape_recorded_no_roster(client):
    """Patches are sparse: patching against a missing base silently reduces every person to
    the fields the reviewer touched, so the save must refuse rather than truncate."""
    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[]),
        patch("database.assertions.create_all", new_callable=AsyncMock) as mock_update,
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/save",
            json={
                "request_id": TEST_REQUEST_ID,
                "jurisdiction_ocdid": TEST_OCDID,
                "data": [{"id": "p1", "fields": {"phones": ["9168085300"]}}],
            },
        )

    assert response.status_code == 409
    mock_update.assert_not_awaited()


@pytest.mark.unit
def test_publish_returns_200_and_queues_no_merge(client):
    """Publishing settles within the request: the roster is written and the entry resolved
    before the response, so there is nothing for the caller to poll."""
    with (
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock) as mock_resolve,
        patch("services.roster_edits.publish_people", new_callable=AsyncMock) as mock_publish,
        patch("services.roster_edits.promote_to_reviewed", new_callable=AsyncMock),
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/publish",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    mock_resolve.assert_awaited_once_with(TEST_REQUEST_ID)
    mock_publish.assert_awaited_once_with(TEST_REQUEST_ID, TEST_OCDID, [BASE_PERSON], "user-id-123")


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


@pytest.mark.unit
def test_save_and_merge_applies_patch_and_normalizes(client):
    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("database.assertions.create_all", new_callable=AsyncMock) as mock_update,
        patch("services.change_logs.record_manual_edits", new_callable=AsyncMock),
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock),
        patch("services.roster_edits.publish_people", new_callable=AsyncMock) as mock_publish,
        patch("services.roster_edits.promote_to_reviewed", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/publish",
            json={
                "request_id": TEST_REQUEST_ID,
                "jurisdiction_ocdid": TEST_OCDID,
                "data": [{"id": "p1", "fields": {"phones": ["9168085300"]}}],
            },
        )

    assert response.status_code == 200
    # The roster handed to publish, which is what goes live — the patched blob it used to be
    # written to is gone, so this is where the overlay is now observable.
    published = mock_publish.await_args.args[2]
    assert published[0]["phones"] == ["(916) 808-5300"]            # edited field, canonicalized
    assert published[0]["name"] == "Jane Doe"                      # untouched
    assert list(published[0].keys()) == list(BASE_PERSON.keys())   # key order preserved


@pytest.mark.unit
def test_save_and_merge_rejects_invalid_field(client):
    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("database.assertions.create_all", new_callable=AsyncMock) as mock_update,
        patch("lib.redis.set", new_callable=AsyncMock),
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/publish",
            json={
                "request_id": TEST_REQUEST_ID,
                "jurisdiction_ocdid": TEST_OCDID,
                "data": [{"id": "p1", "fields": {"phones": ["not-a-phone"]}}],
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["id"] == "p1"
    assert detail[0]["name"] == "Jane Doe"
    assert detail[0]["field"] == "phones"
    mock_update.assert_not_awaited()


# ── save (commit without publishing) tests ────────────────────────────────

SAVE_PATCH = [{"id": "p1", "fields": {"phones": ["9165551234"]}}]


@pytest.mark.unit
def test_save_commits_and_marks_the_entry_saved_without_publishing(client):
    """The whole point of /save: it persists the edit but triggers none of the merge machinery."""
    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("database.assertions.create_all", new_callable=AsyncMock) as mock_update,
        patch("services.change_logs.record_manual_edits", new_callable=AsyncMock) as mock_change_logs,
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock) as mock_save,
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock) as mock_resolve,
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/save",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID, "data": SAVE_PATCH},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    # Two claims from one edited field: the new number accepted, the old one rejected.
    assert len(mock_update.await_args.args[0]) == 2
    mock_change_logs.assert_awaited_once()
    mock_save.assert_awaited_once_with(TEST_REQUEST_ID)

    mock_resolve.assert_not_awaited()


@pytest.mark.unit
def test_reformatting_a_number_the_scrape_already_found_claims_nothing(client):
    """The reviewer retypes `9168085300`; the scrape already had `(916) 808-5300`. Normalizing
    makes them the same value, so there is nothing for a human to have claimed — a save must
    not manufacture an assertion out of a formatting difference."""
    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("database.assertions.create_all", new_callable=AsyncMock) as mock_update,
        patch("services.change_logs.record_manual_edits", new_callable=AsyncMock),
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/save",
            json={
                "request_id": TEST_REQUEST_ID,
                "jurisdiction_ocdid": TEST_OCDID,
                "data": [{"id": "p1", "fields": {"phones": ["9168085300"]}}],
            },
        )

    assert response.status_code == 200
    # Called, with nothing to record — a formatting difference is not a human claim.
    assert mock_update.await_args.args[0] == []


@pytest.mark.unit
def test_save_records_the_edited_field_canonicalized(client):
    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("database.assertions.create_all", new_callable=AsyncMock) as mock_update,
        patch("services.change_logs.record_manual_edits", new_callable=AsyncMock),
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/save",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID, "data": SAVE_PATCH},
        )

    assert response.status_code == 200
    # A save writes claims, not a roster, so what it recorded is the observable: the number the
    # reviewer typed is accepted canonicalized, and the one the scrape found is rejected.
    stated = mock_update.await_args.args[0]
    assert sorted((a.kind, a.value) for a in stated) == [
        ("accept", "(916) 555-1234"),
        ("reject", "(916) 808-5300"),
    ]
    assert {a.field_path for a in stated} == {"phones"}


@pytest.mark.unit
def test_a_person_added_by_hand_becomes_evidence_and_claims(client):
    """Both, and they mean different things. The record is why they are on the roster at all —
    without one the next read derives the roster from sightings and they are gone. The claims
    are what the reviewer said about them, diffed against nothing because the scrape never
    saw them."""
    added = {
        "id": "p2",
        "fields": {
            "id": "p2",
            "name": "Carolyn Robertson Harding",
            "phones": ["9165551234"],
            "emails": [],
            "urls": [],
            "office": {"name": "Mayor", "division_ocdid": None},
            "jurisdiction_ocdid": TEST_OCDID,
            "source_urls": ["https://x.gov/directory"],
            "updated_at": "2026-08-25T00:00:00+00:00",
        },
    }
    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.insert_source_records", new_callable=AsyncMock) as mock_records,
        patch("database.assertions.create_all", new_callable=AsyncMock) as mock_claims,
        patch("services.change_logs.record_manual_edits", new_callable=AsyncMock),
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/save",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID, "data": [added]},
        )

    assert response.status_code == 200
    # One record, for the one page the reviewer cited — and only for the added person.
    written = mock_records.await_args.args[2]
    assert list(written) == ["p2"]
    assert [r["source_url"] for r in written["p2"]] == ["https://x.gov/directory"]

    claims = mock_claims.await_args.args[0]
    theirs = {(c.field_path, c.kind, c.value) for c in claims if c.entity_id == "p2"}
    assert ("name", "accept", "Carolyn Robertson Harding") in theirs
    assert ("phones", "accept", "(916) 555-1234") in theirs
    # `source_urls` is the evidence, not a claim about the world.
    assert not any(field == "source_urls" for field, _, _ in theirs)


@pytest.mark.unit
def test_save_rejects_invalid_field_without_marking_the_entry(client):
    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("database.assertions.create_all", new_callable=AsyncMock) as mock_update,
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock) as mock_save,
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/save",
            json={
                "request_id": TEST_REQUEST_ID,
                "jurisdiction_ocdid": TEST_OCDID,
                "data": [{"id": "p1", "fields": {"phones": ["not-a-phone"]}}],
            },
        )

    assert response.status_code == 422
    mock_update.assert_not_awaited()
    mock_save.assert_not_awaited()


@pytest.mark.unit
def test_save_returns_500_and_does_not_mark_the_entry_when_the_write_fails():
    """The persist is the only thing standing between the reviewer and a lost edit, so a
    failure must not be reported as a save."""
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(pull_requests_router.get_router(None), prefix="/pull_requests")
    # The write raises rather than returning falsy now that it is a DB call, so the 500 has to
    # come from the app rather than from the test client re-raising.
    failing_client = TestClient(app, raise_server_exceptions=False)

    with (
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("database.assertions.create_all", new_callable=AsyncMock, side_effect=RuntimeError("write failed")),
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock) as mock_save,
    ):
        response = failing_client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/save",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID, "data": SAVE_PATCH},
        )

    assert response.status_code == 500
    mock_save.assert_not_awaited()


@pytest.mark.unit
def test_save_requires_data(client):
    response = client.post(
        f"/pull_requests/{TEST_REQUEST_ID}/save",
        json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
    )
    assert response.status_code == 422


# ── get_pull_request_by_number tests ──────────────────────────────────────

OPEN_PR_DB_RESULT = {
    "request_id": TEST_REQUEST_ID,
    "jurisdiction_ocdid": TEST_OCDID,
    "jurisdiction_name": "Oakland",
    "jurisdiction_website_url": "https://oaklandca.gov",
    "pr": {"url": "https://github.com/org/repo/pull/42", "status": "open", "number": 42},
}

MERGED_PR_DB_RESULT = {
    **OPEN_PR_DB_RESULT,
    "pr": {"url": "https://github.com/org/repo/pull/42", "status": "merged", "number": 42},
}


@pytest.mark.unit
def test_get_by_request_404_when_not_found(client):
    with patch(
        "database.pull_requests.get_pull_request_data_by_request_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get("/pull_requests/by-request/req-missing")

    assert response.status_code == 404


@pytest.mark.unit
def test_get_by_request_200_for_open_pr(client):
    with (
        patch(
            "database.pull_requests.get_pull_request_data_by_request_id",
            new_callable=AsyncMock,
            return_value=OPEN_PR_DB_RESULT,
        ),
        patch(
            "database.people.get_people",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "routers.api.pull_requests.proposed_roster",
            new_callable=AsyncMock,
            return_value=[{"name": "Jane Doe"}],
        ),
        patch(
            "database.jurisdictions.get_scraped_at",
            new_callable=AsyncMock,
            return_value=None,
        ),
        # Crosses to the DB for the roster and the memberships it diffs against. The
        # proposal itself is unit-tested in core/test_membership_proposal.py.
        patch(
            "routers.api.pull_requests.proposals_for_requests",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        response = client.get(f"/pull_requests/by-request/{TEST_REQUEST_ID}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["request_id"] == TEST_REQUEST_ID
    assert data["pr"]["status"] == "open"
    assert data["has_next"] is False
    assert data["has_prev"] is False
    # never scraped → baseline mode
    assert data["mode"] == "baseline"


@pytest.mark.unit
def test_get_by_request_200_for_merged_pr(client):
    with (
        patch(
            "database.pull_requests.get_pull_request_data_by_request_id",
            new_callable=AsyncMock,
            return_value=MERGED_PR_DB_RESULT,
        ),
        patch(
            "database.people.get_people",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "routers.api.pull_requests.proposed_roster",
            new_callable=AsyncMock,
            return_value=[{"name": "Jane Doe"}],
        ),
        patch(
            "database.jurisdictions.get_scraped_at",
            new_callable=AsyncMock,
            return_value=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        ),
        # Same DB boundary as the open-pr case above.
        patch(
            "routers.api.pull_requests.proposals_for_requests",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        response = client.get(f"/pull_requests/by-request/{TEST_REQUEST_ID}")

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
        ("delete", f"/pull_requests/{TEST_PR_NUMBER}?request_id={TEST_REQUEST_ID}"),
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
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock),
        patch("services.roster_edits.publish_people", new_callable=AsyncMock),
        patch("services.roster_edits.promote_to_reviewed", new_callable=AsyncMock),
        patch("services.roster_edits.proposed_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("services.roster_edits.scraped_roster", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/publish",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
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
        return_value={"id": "issue-1", "github_issue_url": "https://github.com/org/open-data/issues/9", "github_issue_number": 9},
    ) as mock_report:
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/issues",
            json={"description": "Something looks wrong."},
        )

    assert response.status_code == 200
    assert response.json()["data"]["github_issue_url"] == "https://github.com/org/open-data/issues/9"
    mock_report.assert_awaited_once()


@pytest.mark.unit
def test_report_review_issue_404_when_review_not_found(client):
    with patch(
        "services.review_issue_report.report_review_issue",
        new_callable=AsyncMock,
        side_effect=pull_requests_router.review_issue_report_service.ReviewNotFoundError("no review"),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/issues",
            json={"description": "Something looks wrong."},
        )

    assert response.status_code == 404


@pytest.mark.unit
def test_report_review_issue_502_when_github_fails(client):
    with patch(
        "services.review_issue_report.report_review_issue",
        new_callable=AsyncMock,
        side_effect=pull_requests_router.review_issue_report_service.GithubIssueCreationError("GitHub is down"),
    ):
        response = client.post(
            f"/pull_requests/{TEST_REQUEST_ID}/issues",
            json={"description": "Something looks wrong."},
        )

    assert response.status_code == 502


@pytest.mark.unit
def test_report_review_issue_422_on_empty_description(client):
    response = client.post(
        f"/pull_requests/{TEST_REQUEST_ID}/issues",
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
        f"/pull_requests/{TEST_REQUEST_ID}/issues",
        json={"description": "Something looks wrong."},
    )

    assert response.status_code == 401


@pytest.mark.unit
def test_get_reported_issues_returns_data(client):
    with patch(
        "database.issues.get_user_reported_issues_for_request",
        new_callable=AsyncMock,
        return_value=[{"id": "issue-1", "github_issue_url": "https://github.com/org/open-data/issues/9", "github_issue_number": 9, "status": "pending"}],
    ):
        response = client.get(f"/pull_requests/{TEST_REQUEST_ID}/issues")

    assert response.status_code == 200
    assert response.json()["data"][0]["github_issue_number"] == 9


@pytest.mark.unit
def test_get_reported_issues_allows_default_role():
    """Reviewers (default role) can see issues they've already filed for this
    request — read-only, same gate as the POST that creates them."""
    client = _client_as(_user_at(UserRole.DEFAULT))
    with patch(
        "database.issues.get_user_reported_issues_for_request",
        new_callable=AsyncMock,
        return_value=[],
    ):
        response = client.get(f"/pull_requests/{TEST_REQUEST_ID}/issues")

    assert response.status_code == 200
