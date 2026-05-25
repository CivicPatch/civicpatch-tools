import asyncio
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from schemas.common import Identity, Role
from lib.auth import get_optional_user
from routers.api import pull_requests as pull_requests_router
from core.pull_request_merge import do_merge

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    user_id="user-id-123",
)


def _user_at(role: Role) -> Identity:
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
            "core.pull_request_sync.apply_pull_request_status",
            new_callable=AsyncMock,
        ),
        patch(
            "core.change_logs.record_close",
            new_callable=AsyncMock,
        ),
    ):
        response = client.delete(
            f"/pull_requests/{TEST_PR_NUMBER}",
            params={"request_id": TEST_REQUEST_ID},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


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
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    mock_enqueue.assert_awaited_once()
    assert mock_enqueue.await_args is not None
    sent_request = mock_enqueue.await_args.args[0]
    assert sent_request.pull_request_number == TEST_PR_NUMBER
    assert sent_request.request_id == TEST_REQUEST_ID
    assert sent_request.merge_key == f"merge_status:{TEST_PR_NUMBER}"
    mock_set_enqueued.assert_awaited_once_with(TEST_REQUEST_ID)


# ── get_pull_request_by_number tests ──────────────────────────────────────

OPEN_PR_DB_RESULT = {
    "request_id": TEST_REQUEST_ID,
    "jurisdiction_ocdid": TEST_OCDID,
    "jurisdiction_name": "Oakland",
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
    ):
        response = client.get(f"/pull_requests/by-request/{TEST_REQUEST_ID}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["request_id"] == TEST_REQUEST_ID
    assert data["pr"]["status"] == "open"
    assert data["has_next"] is False
    assert data["has_prev"] is False


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
    ):
        response = client.get(f"/pull_requests/by-request/{TEST_REQUEST_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["pr"]["status"] == "merged"


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
        patch("core.change_logs.record_publish", new_callable=AsyncMock),
        patch("core.pull_request_sync.publish_side_effects", new_callable=AsyncMock) as mock_side_effects,
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "merged"
    mock_side_effects.assert_awaited_once()


@pytest.mark.unit
def test_do_merge_dirty_pr_writes_error_and_clears_in_flight():
    redis_set = AsyncMock()
    clear_enqueued = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="dirty"),
        patch("database.pull_requests.clear_merge_enqueued", clear_enqueued),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "conflicts" in last_call_value["error"]
    clear_enqueued.assert_awaited_once_with(TEST_REQUEST_ID)


@pytest.mark.unit
def test_do_merge_blocked_pr_writes_error():
    redis_set = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="blocked"),
        patch("database.pull_requests.clear_merge_enqueued", new_callable=AsyncMock),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "blocked" in last_call_value["error"]


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
        patch("core.change_logs.record_publish", new_callable=AsyncMock),
        patch("core.pull_request_sync.publish_side_effects", new_callable=AsyncMock),
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
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "unexpected" in last_call_value["error"]


# ── Auth gates on write routes ──────────────────────────────────────────────
#
# These routes were bumped from RouteCategory.AUTHENTICATED to
# (TEAM_REQUIRED, Role.CONTRIBUTORS). The default-level (signed-in but no
# elevation) user must be rejected with 403; the auth-ladder cascade is
# proven separately in test_auth.py, so here we just pin the gate floor.


@pytest.mark.unit
@pytest.mark.parametrize(
    "method,url",
    [
        ("put", "/pull_requests/data"),
        ("delete", f"/pull_requests/{TEST_PR_NUMBER}?request_id={TEST_REQUEST_ID}"),
        ("post", f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge"),
        ("post", f"/pull_requests/{TEST_PR_NUMBER}/merge?request_id={TEST_REQUEST_ID}"),
        ("post", f"/pull_requests/{TEST_PR_NUMBER}/update-branch"),
    ],
)
def test_pull_request_writes_reject_default_role(method, url):
    """Default-level users (just-signed-in, no elevation) must be 403'd from
    every write route that mutates PR state."""
    client = _client_as(_user_at(Role.DEFAULT))
    kwargs = {} if method == "delete" else {"json": {}}
    response = getattr(client, method)(url, **kwargs)
    assert response.status_code == 403
