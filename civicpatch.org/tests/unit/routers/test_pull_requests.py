import asyncio
import datetime
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from schemas.common import Identity, UserRole
from lib.auth import get_optional_user
from routers.api import pull_requests as pull_requests_router
from services.pull_request_merge import do_merge

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
            "database.people.get_people_data_by_request_ids",
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
def test_get_pull_request_review_returns_review_data(client):
    with patch(
        "database.pipeline_runs.get_pipeline_run_result",
        new_callable=AsyncMock,
        return_value={"review_json": {"flagged": [], "notes": "ok"}},
    ):
        response = client.get(f"/pull_requests/{TEST_REQUEST_ID}/review")

    assert response.status_code == 200
    assert "data" in response.json()


@pytest.mark.unit
def test_get_pull_request_review_returns_empty_when_no_result(client):
    with patch(
        "database.pipeline_runs.get_pipeline_run_result",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(f"/pull_requests/{TEST_REQUEST_ID}/review")

    assert response.status_code == 200
    assert response.json()["data"] == {}


@pytest.mark.unit
def test_close_pull_request_returns_success(client):
    with (
        patch(
            "lib.github.api.close_pull_request",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "database.users.get_user_id_by_provider",
            new_callable=AsyncMock,
            return_value="user-id-123",
        ),
        patch(
            "services.pull_request_sync.apply_pull_request_status",
            new_callable=AsyncMock,
        ),
        patch(
            "services.change_logs.record_close",
            new_callable=AsyncMock,
        ),
        patch(
            "database.review_session_entries.resolve_entries_for_request",
            new_callable=AsyncMock,
        ) as mock_resolve,
    ):
        response = client.delete(
            f"/pull_requests/{TEST_PR_NUMBER}",
            params={"request_id": TEST_REQUEST_ID},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_resolve.assert_awaited_once_with(TEST_REQUEST_ID)


@pytest.mark.unit
def test_close_pull_request_returns_500_on_github_failure(client):
    with patch(
        "lib.github.api.close_pull_request",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = client.delete(
            f"/pull_requests/{TEST_PR_NUMBER}",
            params={"request_id": TEST_REQUEST_ID},
        )

    assert response.status_code == 500


@pytest.mark.unit
def test_save_and_merge_returns_202(client):
    with (
        patch("lib.redis.set", new_callable=AsyncMock),
        patch("lib.temporal.client.enqueue_merge", new_callable=AsyncMock) as mock_enqueue,
        patch("database.pull_requests.set_merge_enqueued", new_callable=AsyncMock) as mock_set_enqueued,
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock) as mock_resolve,
        patch("routers.api.pull_requests.publish_people", new_callable=AsyncMock) as mock_publish,
        patch("database.pipeline_runs.get_pipeline_run_data_json", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    mock_resolve.assert_awaited_once_with(TEST_REQUEST_ID)
    mock_enqueue.assert_awaited_once()
    assert mock_enqueue.await_args is not None
    sent_request = mock_enqueue.await_args.args[0]
    assert sent_request.pull_request_number == TEST_PR_NUMBER
    assert sent_request.request_id == TEST_REQUEST_ID
    assert sent_request.merge_key == f"merge_status:{TEST_PR_NUMBER}"
    mock_set_enqueued.assert_awaited_once_with(TEST_REQUEST_ID)
    # Publishing is a DB write at the endpoint now, not a consequence of the merge landing.
    mock_publish.assert_awaited_once_with(TEST_REQUEST_ID, TEST_OCDID, [BASE_PERSON])


# An Official-valid person on the PR branch, in on-disk field order. A patch overlays only
# the edited fields onto this base, so untouched fields and key order stay intact.
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
        patch("lib.github.api.get_pull_request_file_yaml", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("lib.github.api.update_pull_request_file", new_callable=AsyncMock, return_value=True) as mock_update,
        patch("database.pipeline_runs.update_pipeline_run_data", new_callable=AsyncMock),
        patch("services.change_logs.record_manual_edits", new_callable=AsyncMock),
        patch("lib.redis.set", new_callable=AsyncMock),
        patch("lib.temporal.client.enqueue_merge", new_callable=AsyncMock),
        patch("database.pull_requests.set_merge_enqueued", new_callable=AsyncMock),
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock),
        patch("routers.api.pull_requests.publish_people", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge",
            json={
                "request_id": TEST_REQUEST_ID,
                "jurisdiction_ocdid": TEST_OCDID,
                "data": [{"id": "p1", "fields": {"phones": ["9168085300"]}}],
            },
        )

    assert response.status_code == 202
    sent = mock_update.await_args.kwargs["new_data"]
    assert sent[0]["phones"] == ["(916) 808-5300"]            # edited field, canonicalized
    assert sent[0]["name"] == "Jane Doe"                      # untouched
    assert list(sent[0].keys()) == list(BASE_PERSON.keys())   # key order preserved


@pytest.mark.unit
def test_save_and_merge_rejects_invalid_field(client):
    with (
        patch("lib.github.api.get_pull_request_file_yaml", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("lib.github.api.update_pull_request_file", new_callable=AsyncMock) as mock_update,
        patch("lib.redis.set", new_callable=AsyncMock),
        patch("lib.temporal.client.enqueue_merge", new_callable=AsyncMock),
        patch("database.pull_requests.set_merge_enqueued", new_callable=AsyncMock),
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge",
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

SAVE_PATCH = [{"id": "p1", "fields": {"phones": ["9168085300"]}}]


@pytest.mark.unit
def test_save_commits_and_marks_the_entry_saved_without_publishing(client):
    """The whole point of /save: it writes the branch but triggers none of the merge machinery."""
    with (
        patch("lib.github.api.get_pull_request_file_yaml", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("lib.github.api.update_pull_request_file", new_callable=AsyncMock, return_value=True) as mock_update,
        patch("database.pipeline_runs.update_pipeline_run_data", new_callable=AsyncMock),
        patch("services.change_logs.record_manual_edits", new_callable=AsyncMock) as mock_change_logs,
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock) as mock_save,
        patch("lib.temporal.client.enqueue_merge", new_callable=AsyncMock) as mock_enqueue,
        patch("database.pull_requests.set_merge_enqueued", new_callable=AsyncMock) as mock_set_enqueued,
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock) as mock_resolve,
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID, "data": SAVE_PATCH},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    mock_update.assert_awaited_once()
    mock_change_logs.assert_awaited_once()
    mock_save.assert_awaited_once_with(TEST_REQUEST_ID)

    mock_enqueue.assert_not_awaited()
    mock_set_enqueued.assert_not_awaited()
    mock_resolve.assert_not_awaited()


@pytest.mark.unit
def test_save_applies_the_patch_against_the_branch_file(client):
    with (
        patch("lib.github.api.get_pull_request_file_yaml", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("lib.github.api.update_pull_request_file", new_callable=AsyncMock, return_value=True) as mock_update,
        patch("database.pipeline_runs.update_pipeline_run_data", new_callable=AsyncMock),
        patch("services.change_logs.record_manual_edits", new_callable=AsyncMock),
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID, "data": SAVE_PATCH},
        )

    assert response.status_code == 200
    sent = mock_update.await_args.kwargs["new_data"]
    assert sent[0]["phones"] == ["(916) 808-5300"]            # edited field, canonicalized
    assert sent[0]["name"] == "Jane Doe"                      # untouched
    assert list(sent[0].keys()) == list(BASE_PERSON.keys())   # key order preserved


@pytest.mark.unit
def test_save_rejects_invalid_field_without_marking_the_entry(client):
    with (
        patch("lib.github.api.get_pull_request_file_yaml", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("lib.github.api.update_pull_request_file", new_callable=AsyncMock) as mock_update,
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock) as mock_save,
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save",
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
def test_save_returns_500_and_does_not_mark_the_entry_when_the_commit_fails(client):
    with (
        patch("lib.github.api.get_pull_request_file_yaml", new_callable=AsyncMock, return_value=[{**BASE_PERSON}]),
        patch("lib.github.api.update_pull_request_file", new_callable=AsyncMock, return_value=False),
        patch("database.review_session_entries.save_entries_for_request", new_callable=AsyncMock) as mock_save,
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID, "data": SAVE_PATCH},
        )

    assert response.status_code == 500
    mock_save.assert_not_awaited()


@pytest.mark.unit
def test_save_requires_data(client):
    response = client.post(
        f"/pull_requests/{TEST_PR_NUMBER}/save",
        json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
    )
    assert response.status_code == 422


# ── get_pull_request_by_number tests ──────────────────────────────────────

OPEN_PR_DB_RESULT = {
    "request_id": TEST_REQUEST_ID,
    "jurisdiction_ocdid": TEST_OCDID,
    "jurisdiction_name": "Oakland",
    "jurisdiction_website_url": "https://oaklandca.gov",
    "pr": {"url": "https://github.com/org/repo/pull/42", "status": "open", "review_state": None, "number": 42},
    "proposed": [{"name": "Jane Doe"}],
}

MERGED_PR_DB_RESULT = {
    **OPEN_PR_DB_RESULT,
    "pr": {"url": "https://github.com/org/repo/pull/42", "status": "merged", "review_state": None, "number": 42},
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
            "database.people.get_people_by_jurisdiction_ocdid",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "database.jurisdictions.get_scraped_at",
            new_callable=AsyncMock,
            return_value=None,
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
            "database.people.get_people_by_jurisdiction_ocdid",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "database.jurisdictions.get_scraped_at",
            new_callable=AsyncMock,
            return_value=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
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


@pytest.mark.unit
def test_do_merge_clean_pr_writes_merged():
    redis_set = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="clean"),
        patch("lib.github.api.merge_pull_request", new_callable=AsyncMock, return_value=None),
        patch("lib.github.api.get_pull_request", new_callable=AsyncMock, return_value={"labels": []}),
        patch("database.pull_requests.update_pull_request_status", new_callable=AsyncMock),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
        patch("services.change_logs.record_publish", new_callable=AsyncMock),
        patch("services.pull_request_sync.publish_side_effects", new_callable=AsyncMock) as mock_side_effects,
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "merged"
    mock_side_effects.assert_awaited_once()


@pytest.mark.unit
def test_do_merge_dirty_pr_keeps_park_and_raises_issue():
    redis_set = AsyncMock()
    clear_enqueued = AsyncMock()
    upsert_issue = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="dirty"),
        patch("database.pull_requests.clear_merge_enqueued", clear_enqueued),
        patch("database.issues.upsert_issue", upsert_issue),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "conflicts" in last_call_value["error"]
    # A failed merge stays parked (merge_enqueued_at NOT cleared) and surfaces as a
    # merge_failed issue for an admin to dismiss.
    clear_enqueued.assert_not_awaited()
    upsert_issue.assert_awaited_once()
    _, _, issues = upsert_issue.call_args.args
    assert issues[0]["mergeable_state"] == "dirty"


@pytest.mark.unit
def test_do_merge_blocked_pr_writes_error():
    redis_set = AsyncMock()
    upsert_issue = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="blocked"),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
        patch("database.issues.upsert_issue", upsert_issue),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "blocked" in last_call_value["error"]
    _, _, issues = upsert_issue.call_args.args
    assert issues[0]["mergeable_state"] == "blocked"


@pytest.mark.unit
def test_do_merge_null_mergeability_records_state():
    # GitHub never finished computing mergeability within the poll window: the issue
    # records mergeable_state=None so the details page shows a timeout, not a bare id.
    redis_set = AsyncMock()
    upsert_issue = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value=None),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
        patch("database.issues.upsert_issue", upsert_issue),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    _, _, issues = upsert_issue.call_args.args
    assert issues[0]["mergeable_state"] is None


@pytest.mark.unit
def test_do_merge_behind_pr_updates_branch_and_merges():
    redis_set = AsyncMock()
    mergeability = AsyncMock(side_effect=["behind", "clean"])
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", mergeability),
        patch("lib.github.api.update_pull_request_branch", new_callable=AsyncMock, return_value=None),
        patch("lib.github.api.merge_pull_request", new_callable=AsyncMock, return_value=None),
        patch("lib.github.api.get_pull_request", new_callable=AsyncMock, return_value={"labels": []}),
        patch("database.pull_requests.update_pull_request_status", new_callable=AsyncMock),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
        patch("services.change_logs.record_publish", new_callable=AsyncMock),
        patch("services.pull_request_sync.publish_side_effects", new_callable=AsyncMock),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "merged"


@pytest.mark.unit
def test_do_merge_behind_pr_dirty_after_update_writes_error():
    redis_set = AsyncMock()
    mergeability = AsyncMock(side_effect=["behind", "dirty"])
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", mergeability),
        patch("lib.github.api.update_pull_request_branch", new_callable=AsyncMock, return_value=None),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
        patch("database.issues.upsert_issue", new_callable=AsyncMock),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "conflicts" in last_call_value["error"]


@pytest.mark.unit
def test_do_merge_github_error_writes_error():
    redis_set = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="clean"),
        patch("lib.github.api.merge_pull_request", new_callable=AsyncMock, return_value="GitHub API error"),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
        patch("database.issues.upsert_issue", new_callable=AsyncMock),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert last_call_value["error"] == "GitHub API error"


@pytest.mark.unit
def test_do_merge_behind_pr_update_branch_error_writes_error():
    redis_set = AsyncMock()
    mergeability = AsyncMock(return_value="behind")
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", mergeability),
        patch("lib.github.api.update_pull_request_branch", new_callable=AsyncMock, return_value="branch update failed"),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
        patch("database.issues.upsert_issue", new_callable=AsyncMock),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert last_call_value["error"] == "branch update failed"


@pytest.mark.unit
def test_do_merge_unexpected_exception_writes_error():
    redis_set = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", side_effect=RuntimeError("boom")),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
        patch("database.issues.upsert_issue", new_callable=AsyncMock),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "unexpected" in last_call_value["error"]


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
        ("post", f"/pull_requests/{TEST_PR_NUMBER}/merge?request_id={TEST_REQUEST_ID}"),
        ("post", f"/pull_requests/{TEST_PR_NUMBER}/update-branch"),
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
def test_save_and_merge_allows_default_role():
    """A default-role reviewer may publish (save & merge) the PR they're
    reviewing — the route is AUTHENTICATED, not contributor-gated."""
    client = _client_as(_user_at(UserRole.DEFAULT))
    with (
        patch("lib.redis.set", new_callable=AsyncMock),
        patch("lib.temporal.client.enqueue_merge", new_callable=AsyncMock),
        patch("database.pull_requests.set_merge_enqueued", new_callable=AsyncMock),
        patch("database.review_session_entries.resolve_entries_for_request", new_callable=AsyncMock),
        patch("routers.api.pull_requests.publish_people", new_callable=AsyncMock),
        patch("database.pipeline_runs.get_pipeline_run_data_json", new_callable=AsyncMock, return_value=[]),
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 202


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
