import asyncio
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from schemas.common import Identity, Role
from utils.auth_utils import get_optional_user
from routers.api import pull_requests as pull_requests_router
from routers.api.pull_requests import do_merge

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    teams=[Role.CONTRIBUTORS, Role.MAINTAINERS, Role.ADMINS, Role.DEFAULT],
    user_id="user-id-123",
)

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
        "database.jobs.get_job_result",
        new_callable=AsyncMock,
        return_value={"review_json": {"flagged": [], "notes": "ok"}},
    ):
        response = client.get(f"/pull_requests/{TEST_REQUEST_ID}/review")

    assert response.status_code == 200
    assert "data" in response.json()


@pytest.mark.unit
def test_get_pull_request_review_returns_empty_when_no_result(client):
    with patch(
        "database.jobs.get_job_result",
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
            "database.pull_requests.update_job_pull_request_status",
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
        patch("routers.api.pull_requests.do_merge", new_callable=AsyncMock),
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"


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
        patch("database.pull_requests.update_job_pull_request_status", new_callable=AsyncMock),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "merged"


@pytest.mark.unit
def test_do_merge_dirty_pr_writes_error():
    redis_set = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="dirty"),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "conflicts" in last_call_value["error"]


@pytest.mark.unit
def test_do_merge_blocked_pr_writes_error():
    redis_set = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="blocked"),
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
        patch("database.pull_requests.update_job_pull_request_status", new_callable=AsyncMock),
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
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "conflicts" in last_call_value["error"]


@pytest.mark.unit
def test_do_merge_base_branch_modified_retries_and_succeeds():
    redis_set = AsyncMock()
    merge = AsyncMock(side_effect=["Base branch was modified. Review and try the merge again.", None])
    mergeability = AsyncMock(side_effect=["clean", "clean"])
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", mergeability),
        patch("lib.github.api.merge_pull_request", merge),
        patch("lib.github.api.update_pull_request_branch", new_callable=AsyncMock, return_value=None),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("database.pull_requests.update_job_pull_request_status", new_callable=AsyncMock),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "merged"


@pytest.mark.unit
def test_do_merge_github_error_writes_error():
    redis_set = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", new_callable=AsyncMock, return_value="clean"),
        patch("lib.github.api.merge_pull_request", new_callable=AsyncMock, return_value="GitHub API error"),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert last_call_value["error"] == "GitHub API error"


@pytest.mark.unit
def test_do_merge_unexpected_exception_writes_error():
    redis_set = AsyncMock()
    with (
        patch("lib.redis.set", redis_set),
        patch("lib.github.api.get_pull_request_mergeability", side_effect=RuntimeError("boom")),
    ):
        run(do_merge(TEST_PR_NUMBER, TEST_REQUEST_ID, "test@civicpatch.org", "user-id-123", MERGE_KEY))

    last_call_value = json.loads(redis_set.call_args[0][1])
    assert last_call_value["status"] == "error"
    assert "unexpected" in last_call_value["error"]
