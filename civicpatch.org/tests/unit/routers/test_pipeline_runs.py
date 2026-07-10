import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from schemas.common import Identity
from lib.auth import get_optional_user
from routers.api import pipeline_runs as pipeline_runs_router
from routers.api.pipeline_runs import update_pipeline_run_and_publish

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
)

TEST_REQUEST_ID = "test-request-id-123"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(pipeline_runs_router.get_router(None), prefix="/pipeline_runs")
    return TestClient(app)


@pytest.mark.unit
def test_create_job_returns_request_id(client):
    with patch(
        "routers.api.pipeline_runs.has_open_pr_for_jurisdiction",
        new_callable=AsyncMock,
        return_value=False,
    ), patch(
        "routers.api.pipeline_runs.register_request_with_pipeline_run",
        new_callable=AsyncMock,
    ), patch(
        "routers.api.pipeline_runs.temporal_service.start_people_collector_workflow",
        new_callable=AsyncMock,
        return_value="people-collector-ocd-jurisdiction-country-us-state-ca-place-oakland",
    ):
        response = client.post(
            "/pipeline_runs/",
            json={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert "status" in data


@pytest.mark.unit
def test_create_job_returns_500_on_temporal_error(client):
    with patch(
        "routers.api.pipeline_runs.has_open_pr_for_jurisdiction",
        new_callable=AsyncMock,
        return_value=False,
    ), patch(
        "routers.api.pipeline_runs.register_request_with_pipeline_run",
        new_callable=AsyncMock,
    ), patch(
        "routers.api.pipeline_runs.temporal_service.start_people_collector_workflow",
        new_callable=AsyncMock,
        side_effect=Exception("Temporal unavailable"),
    ):
        response = client.post(
            "/pipeline_runs/",
            json={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 500


@pytest.mark.unit
def test_create_job_returns_409_when_open_pr_exists(client):
    with patch(
        "routers.api.pipeline_runs.has_open_pr_for_jurisdiction",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = client.post(
            "/pipeline_runs/",
            json={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 409


@pytest.mark.unit
def test_get_pipeline_run_status_returns_status(client):
    with patch(
        "routers.api.pipeline_runs.get_pipeline_run_status",
        new_callable=AsyncMock,
        return_value={"status": "running", "progress": 42},
    ):
        response = client.get(f"/pipeline_runs/{TEST_REQUEST_ID}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["progress"] == 42


@pytest.mark.unit
def test_get_pipeline_run_status_returns_404_when_not_found(client):
    with patch(
        "routers.api.pipeline_runs.get_pipeline_run_status",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(f"/pipeline_runs/{TEST_REQUEST_ID}/status")

    assert response.status_code == 404


@pytest.mark.unit
def test_patch_job_status_returns_updated_status(client):
    with patch("routers.api.pipeline_runs.update_pipeline_run_and_publish", new_callable=AsyncMock):
        response = client.patch(
            f"/pipeline_runs/{TEST_REQUEST_ID}/status",
            json={"status": "complete", "progress": 100},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["request_id"] == TEST_REQUEST_ID


@pytest.mark.unit
def test_post_job_result_returns_request_id(client):
    with (
        patch("routers.api.pipeline_runs.update_pipeline_run_data", new_callable=AsyncMock, return_value=True),
    ):
        response = client.post(
            f"/pipeline_runs/{TEST_REQUEST_ID}/result",
            json={"data": {"people": []}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == TEST_REQUEST_ID
    assert "errors" in data




@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_pipeline_run_and_publish_publishes_when_jurisdiction_provided():
    with (
        patch("routers.api.pipeline_runs.update_pipeline_run_status", new_callable=AsyncMock) as mock_update,
        patch("routers.api.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock) as mock_publish,
    ):
        await update_pipeline_run_and_publish(TEST_REQUEST_ID, "running", 50, "ocd-division/country:us/state:ca/place:oakland")

        mock_update.assert_awaited_once_with(request_id=TEST_REQUEST_ID, status="running", progress=50)
        mock_publish.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_pipeline_run_and_publish_skips_publish_when_no_jurisdiction():
    with (
        patch("routers.api.pipeline_runs.update_pipeline_run_status", new_callable=AsyncMock),
        patch("routers.api.pipeline_runs.get_pipeline_run", new_callable=AsyncMock, return_value=None),
        patch("database.database.get_pool", new_callable=AsyncMock),
        patch("routers.api.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock) as mock_publish,
    ):
        await update_pipeline_run_and_publish(TEST_REQUEST_ID, "running", 50, None)

        mock_publish.assert_not_awaited()


@pytest.mark.unit
def test_get_context_upload_url_returns_url(client):
    with patch(
        "routers.api.pipeline_runs.storage_service.get_presigned_put_url",
        return_value="https://storage.example.com/presigned-put",
    ):
        response = client.get(f"/pipeline_runs/{TEST_REQUEST_ID}/context/upload-url")

    assert response.status_code == 200
    assert response.json()["url"] == "https://storage.example.com/presigned-put"


@pytest.mark.unit
def test_get_context_download_url_returns_url(client):
    with patch(
        "routers.api.pipeline_runs.storage_service.get_presigned_url_cached",
        return_value="https://storage.example.com/presigned-get",
    ):
        response = client.get(f"/pipeline_runs/{TEST_REQUEST_ID}/context/download-url")

    assert response.status_code == 200
    assert response.json()["url"] == "https://storage.example.com/presigned-get"


@pytest.mark.unit
def test_delete_context_returns_request_id(client):
    with patch("routers.api.pipeline_runs.storage_service.delete_object"):
        response = client.delete(f"/pipeline_runs/{TEST_REQUEST_ID}/context")

    assert response.status_code == 200
    assert response.json()["request_id"] == TEST_REQUEST_ID


@pytest.mark.unit
def test_get_issues_returns_paginated_list(client):
    with patch(
        "routers.api.pipeline_runs.get_issues_page",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        response = client.get("/pipeline_runs/issues")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data


@pytest.mark.unit
def test_dismiss_merge_failed_issue_unparks_pr(client):
    """Dismissing a merge_failed issue clears the PR's merge park so it returns to the pool."""
    issue = {"id": "issue-1", "issue_type": "merge_failed", "request_ids": [TEST_REQUEST_ID], "status": "pending"}
    clear_enqueued = AsyncMock()
    with (
        patch("routers.api.pipeline_runs.get_issue_by_id", new_callable=AsyncMock, return_value=issue),
        patch("routers.api.pipeline_runs.resolve_issue", new_callable=AsyncMock),
        patch("routers.api.pipeline_runs.clear_merge_enqueued", clear_enqueued),
    ):
        response = client.post("/pipeline_runs/issues/issue-1/dismiss")

    assert response.status_code == 200
    clear_enqueued.assert_awaited_once_with(TEST_REQUEST_ID)


@pytest.mark.unit
def test_dismiss_non_merge_issue_leaves_park_untouched(client):
    """Dismissing any non-merge issue must not touch merge_enqueued_at."""
    issue = {"id": "issue-2", "issue_type": "unrecognized_role", "request_ids": [TEST_REQUEST_ID], "status": "pending"}
    clear_enqueued = AsyncMock()
    with (
        patch("routers.api.pipeline_runs.get_issue_by_id", new_callable=AsyncMock, return_value=issue),
        patch("routers.api.pipeline_runs.resolve_issue", new_callable=AsyncMock),
        patch("routers.api.pipeline_runs.clear_merge_enqueued", clear_enqueued),
    ):
        response = client.post("/pipeline_runs/issues/issue-2/dismiss")

    assert response.status_code == 200
    clear_enqueued.assert_not_awaited()
