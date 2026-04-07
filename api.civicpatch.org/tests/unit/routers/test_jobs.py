import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from schemas.common import Identity, Role
from utils.auth_utils import get_optional_user
from routers.api import jobs as jobs_router
from routers.api.jobs import update_and_publish

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    teams=[Role.CONTRIBUTORS, Role.MAINTAINERS, Role.ADMINS, Role.DEFAULT],
)

TEST_REQUEST_ID = "test-request-id-123"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(jobs_router.get_router(None), prefix="/jobs")
    return TestClient(app)


@pytest.mark.unit
def test_create_job_returns_request_id(client):
    with patch(
        "routers.api.jobs.temporal_service.start_people_collector_workflow",
        new_callable=AsyncMock,
        return_value="people-collector-ocd-jurisdiction-country-us-state-ca-place-oakland",
    ):
        response = client.post(
            "/jobs/",
            json={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert "status" in data


@pytest.mark.unit
def test_create_job_returns_500_on_temporal_error(client):
    with patch(
        "routers.api.jobs.temporal_service.start_people_collector_workflow",
        new_callable=AsyncMock,
        side_effect=Exception("Temporal unavailable"),
    ):
        response = client.post(
            "/jobs/",
            json={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 500


@pytest.mark.unit
def test_get_job_status_returns_status(client):
    with patch(
        "routers.api.jobs.get_job_status",
        new_callable=AsyncMock,
        return_value={"status": "running", "progress": 42},
    ):
        response = client.get(f"/jobs/{TEST_REQUEST_ID}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["progress"] == 42


@pytest.mark.unit
def test_get_job_status_returns_404_when_not_found(client):
    with patch(
        "routers.api.jobs.get_job_status",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(f"/jobs/{TEST_REQUEST_ID}/status")

    assert response.status_code == 404


@pytest.mark.unit
def test_patch_job_status_returns_updated_status(client):
    with (
        patch("routers.api.jobs.update_job_status", new_callable=AsyncMock),
        patch("routers.api.jobs.pubsub_service.publish", new_callable=AsyncMock),
    ):
        response = client.patch(
            f"/jobs/{TEST_REQUEST_ID}/status",
            json={"status": "complete", "progress": 100},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["request_id"] == TEST_REQUEST_ID


@pytest.mark.unit
def test_post_job_result_returns_request_id(client):
    with (
        patch("routers.api.jobs.update_job_data", new_callable=AsyncMock, return_value=True),
    ):
        response = client.post(
            f"/jobs/{TEST_REQUEST_ID}/result",
            json={"data": {"people": []}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == TEST_REQUEST_ID
    assert "errors" in data


@pytest.mark.unit
def test_get_jobs_with_errors_returns_list(client):
    with (
        patch(
            "routers.api.jobs.get_jobs_with_errors",
            new_callable=AsyncMock,
            return_value=[
                {
                    "request_id": TEST_REQUEST_ID,
                    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland",
                    "status": "error",
                }
            ],
        ),
        patch("routers.api.jobs.shared.utils.id_utils.jurisdiction_ocdid_to_folder", return_value="us/ca/oakland"),
    ):
        response = client.get("/jobs/errors")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_and_publish_publishes_when_jurisdiction_provided():
    with (
        patch("routers.api.jobs.update_job_status", new_callable=AsyncMock) as mock_update,
        patch("routers.api.jobs.pubsub_service.publish", new_callable=AsyncMock) as mock_publish,
    ):
        await update_and_publish(TEST_REQUEST_ID, "running", 50, "ocd-division/country:us/state:ca/place:oakland")

        mock_update.assert_awaited_once_with(request_id=TEST_REQUEST_ID, status="running", progress=50)
        mock_publish.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_and_publish_skips_publish_when_no_jurisdiction():
    with (
        patch("routers.api.jobs.update_job_status", new_callable=AsyncMock),
        patch("routers.api.jobs.pubsub_service.publish", new_callable=AsyncMock) as mock_publish,
    ):
        await update_and_publish(TEST_REQUEST_ID, "running", 50, None)

        mock_publish.assert_not_awaited()


@pytest.mark.unit
def test_get_job_events_returns_paginated_list(client):
    with patch(
        "routers.api.jobs.get_job_events_page",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        response = client.get("/jobs/events")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
