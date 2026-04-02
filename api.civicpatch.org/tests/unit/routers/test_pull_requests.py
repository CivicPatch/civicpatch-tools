import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from schemas.common import Identity, Role
from utils.auth_utils import get_optional_user
from routers.api import pull_requests as pull_requests_router

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
        "database.database.get_job_result",
        new_callable=AsyncMock,
        return_value={"review_json": {"flagged": [], "notes": "ok"}},
    ):
        response = client.get(f"/pull_requests/{TEST_REQUEST_ID}/review")

    assert response.status_code == 200
    assert "data" in response.json()


@pytest.mark.unit
def test_get_pull_request_review_returns_empty_when_no_result(client):
    with patch(
        "database.database.get_job_result",
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
            "services.github.github_api_service.close_pull_request",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "database.database.get_user_id_by_provider",
            new_callable=AsyncMock,
            return_value="user-id-123",
        ),
        patch(
            "database.database.update_job_pull_request_status",
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
        "services.github.github_api_service.close_pull_request",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = client.delete(
            f"/pull_requests/{TEST_PR_NUMBER}",
            params={"request_id": TEST_REQUEST_ID},
        )

    assert response.status_code == 500


@pytest.mark.unit
def test_save_and_merge_returns_success_on_clean_pr(client):
    with (
        patch(
            "services.github.github_api_service.get_pull_request_mergeability",
            new_callable=AsyncMock,
            return_value="clean",
        ),
        patch(
            "services.github.github_api_service.merge_pull_request",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "database.database.get_user_id_by_provider",
            new_callable=AsyncMock,
            return_value="user-id-123",
        ),
        patch(
            "database.database.update_job_pull_request_status",
            new_callable=AsyncMock,
        ),
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.unit
def test_save_and_merge_returns_422_on_dirty_pr(client):
    with patch(
        "services.github.github_api_service.get_pull_request_mergeability",
        new_callable=AsyncMock,
        return_value="dirty",
    ):
        response = client.post(
            f"/pull_requests/{TEST_PR_NUMBER}/save-and-merge",
            json={"request_id": TEST_REQUEST_ID, "jurisdiction_ocdid": TEST_OCDID},
        )

    assert response.status_code == 422
