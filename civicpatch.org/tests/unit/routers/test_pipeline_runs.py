import pytest
from shared.utils.statuses import DismissalReason
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity
from lib.auth import get_optional_user
from routers.api import pipeline_runs as pipeline_runs_router
from routers.api.pipeline_runs import apply_pipeline_run_status

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
)

TEST_CHANGESET_ID = "test-request-id-123"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(pipeline_runs_router.get_router(None), prefix="/pipeline_runs")
    return TestClient(app)


@pytest.mark.unit
def test_create_job_returns_changeset_id(client):
    with patch(
        "routers.api.pipeline_runs.has_open_changeset",
        new_callable=AsyncMock,
        return_value=False,
    ), patch(
        "routers.api.pipeline_runs.register_run",
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
    assert "changeset_id" in data
    assert "status" in data


@pytest.mark.unit
def test_create_job_returns_500_on_temporal_error(client):
    with patch(
        "routers.api.pipeline_runs.has_open_changeset",
        new_callable=AsyncMock,
        return_value=False,
    ), patch(
        "routers.api.pipeline_runs.register_run",
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
        "routers.api.pipeline_runs.has_open_changeset",
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
        response = client.get(f"/pipeline_runs/{TEST_CHANGESET_ID}/status")

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
        response = client.get(f"/pipeline_runs/{TEST_CHANGESET_ID}/status")

    assert response.status_code == 404


@pytest.mark.unit
def test_patch_job_status_returns_updated_status(client):
    with patch("routers.api.pipeline_runs.apply_pipeline_run_status", new_callable=AsyncMock):
        response = client.patch(
            f"/pipeline_runs/{TEST_CHANGESET_ID}/status",
            json={"status": "complete", "progress": 100},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["changeset_id"] == TEST_CHANGESET_ID


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apply_pipeline_run_status_publishes_when_jurisdiction_provided():
    with (
        patch("routers.api.pipeline_runs.update_pipeline_run_status", new_callable=AsyncMock) as mock_update,
        patch("routers.api.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock) as mock_publish,
    ):
        await apply_pipeline_run_status(TEST_CHANGESET_ID, "running", 50, "ocd-division/country:us/state:ca/place:oakland")

        mock_update.assert_awaited_once_with(run_id=TEST_CHANGESET_ID, status="running", progress=50)
        mock_publish.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apply_pipeline_run_status_skips_publish_when_no_jurisdiction():
    with (
        patch("routers.api.pipeline_runs.update_pipeline_run_status", new_callable=AsyncMock),
        patch("routers.api.pipeline_runs.get_pipeline_run", new_callable=AsyncMock, return_value=None),
        patch("database.database.get_pool", new_callable=AsyncMock),
        patch("routers.api.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock) as mock_publish,
    ):
        await apply_pipeline_run_status(TEST_CHANGESET_ID, "running", 50, None)

        mock_publish.assert_not_awaited()


@pytest.mark.unit
def test_get_context_upload_url_returns_url(client):
    with patch(
        "routers.api.pipeline_runs.storage_service.get_presigned_put_url",
        return_value="https://storage.example.com/presigned-put",
    ):
        response = client.get(f"/pipeline_runs/{TEST_CHANGESET_ID}/context/upload-url")

    assert response.status_code == 200
    assert response.json()["url"] == "https://storage.example.com/presigned-put"


@pytest.mark.unit
def test_get_context_download_url_returns_url(client):
    with patch(
        "routers.api.pipeline_runs.storage_service.get_presigned_url_cached",
        return_value="https://storage.example.com/presigned-get",
    ):
        response = client.get(f"/pipeline_runs/{TEST_CHANGESET_ID}/context/download-url")

    assert response.status_code == 200
    assert response.json()["url"] == "https://storage.example.com/presigned-get"


@pytest.mark.unit
def test_delete_context_returns_changeset_id(client):
    with patch("routers.api.pipeline_runs.storage_service.delete_object"):
        response = client.delete(f"/pipeline_runs/{TEST_CHANGESET_ID}/context")

    assert response.status_code == 200
    assert response.json()["changeset_id"] == TEST_CHANGESET_ID


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


# ── POST /pipeline_runs/{changeset_id}/cancel ───────────────────────────────────

TEST_OCDID = "ocd-jurisdiction/country:us/state:wa/place:buckley/government"


def _cancel_mocks(pipeline_run={"arguments_json": {"jurisdiction_ocdid": TEST_OCDID}}):
    return (
        patch("routers.api.pipeline_runs.get_pipeline_run", new_callable=AsyncMock, return_value=pipeline_run),
        patch("routers.api.pipeline_runs.temporal_service.cancel_workflow", new_callable=AsyncMock),
        patch("routers.api.pipeline_runs.update_pipeline_run_status", new_callable=AsyncMock),
        patch("database.users.get_user_id_by_provider", new_callable=AsyncMock, return_value="user-1"),
        patch("routers.api.pipeline_runs.dismiss_request", new_callable=AsyncMock),
    )


@pytest.mark.unit
def test_cancel_settles_the_review_as_well_as_the_run():
    """Cancelling is a person deciding this scrape will not be published. Without the dismissal
    the request sits at "pending" forever: nothing reviews a run that never finished, so no
    later action would ever resolve it."""
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(pipeline_runs_router.get_router(None), prefix="/pipeline_runs")
    client = TestClient(app)

    get_run, cancel_wf, update_status, get_user, dismiss = _cancel_mocks()
    with get_run, cancel_wf as mock_cancel, update_status as mock_status, get_user, dismiss as mock_dismiss:
        response = client.post(f"/pipeline_runs/{TEST_CHANGESET_ID}/cancel")

    assert response.status_code == 200
    mock_cancel.assert_awaited_once_with(TEST_OCDID)
    assert mock_status.await_args.kwargs["status"] == "CANCELLED"
    mock_dismiss.assert_awaited_once_with(
        TEST_CHANGESET_ID, DismissalReason.CANCELLED, resolved_by_user_id="user-1"
    )


@pytest.mark.unit
def test_cancel_does_not_dismiss_when_the_workflow_refuses_to_stop():
    """A failed cancel leaves the run alone; recording it as dismissed would claim a decision
    that did not take effect."""
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(pipeline_runs_router.get_router(None), prefix="/pipeline_runs")
    client = TestClient(app)

    get_run, _, update_status, get_user, dismiss = _cancel_mocks()
    with (
        get_run,
        patch("routers.api.pipeline_runs.temporal_service.cancel_workflow",
              new_callable=AsyncMock, side_effect=RuntimeError("temporal down")),
        update_status,
        get_user,
        dismiss as mock_dismiss,
    ):
        response = client.post(f"/pipeline_runs/{TEST_CHANGESET_ID}/cancel")

    assert response.status_code == 500
    mock_dismiss.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["CANCELLED", "ERROR"])
async def test_a_run_that_ended_without_a_roster_settles_its_request(status):
    """Both leave nothing to review, so both have to stop counting as pending work — the
    jurisdiction page lists pending requests and `peopleEditBlockers` disables editing from the
    same set, so a failure left a permanent blocker behind."""
    with (
        patch("routers.api.pipeline_runs.dismiss_request", new_callable=AsyncMock) as dismiss,
        patch(
            "routers.api.pipeline_runs.supersede_prior_jurisdiction_issues",
            new_callable=AsyncMock,
        ),
    ):
        await pipeline_runs_router.finalize_pipeline_run(TEST_CHANGESET_ID, status, TEST_OCDID)

    # No user id: a machine giving up, not a person declining. The reason is passed rather
    # than inferred later, because `status` is mutable and a guess could drift.
    dismiss.assert_awaited_once_with(TEST_CHANGESET_ID, DismissalReason.ERRORED)


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["SUCCESS", "RESOLVED"])
async def test_a_run_that_produced_something_is_left_for_review(status):
    """The whole point of the queue. Dismissing a successful run would discard a roster nobody
    had looked at."""
    with (
        patch("routers.api.pipeline_runs.dismiss_request", new_callable=AsyncMock) as dismiss,
        patch(
            "routers.api.pipeline_runs.supersede_prior_jurisdiction_issues",
            new_callable=AsyncMock,
        ),
    ):
        await pipeline_runs_router.finalize_pipeline_run(TEST_CHANGESET_ID, status, TEST_OCDID)

    dismiss.assert_not_awaited()


# ── POST /batch — one durable workflow per state ─────────────────────────────
# It used to select candidates and register a changeset each *before* starting Temporal, which
# left orphans whenever the caller died in between and could not be driven by a Schedule.


@pytest.mark.unit
def test_batch_starts_a_workflow_and_does_not_pick_candidates(client):
    """The workflow finds its own work. If the route still resolved candidates, a scheduled
    scrape — which can only pass a state — would have no way to reach the same path."""
    with patch(
        "routers.api.pipeline_runs.temporal_service.start_state_scrape_workflow",
        new_callable=AsyncMock,
        return_value="state-scrape-wa",
    ) as start, patch(
        "routers.api.pipeline_runs.candidate_service.claim_scrape_candidates",
        new_callable=AsyncMock,
    ) as claim:
        response = client.post("/pipeline_runs/batch", json={"state": "wa"})

    assert response.status_code == 200
    assert response.json()["data"]["workflow_id"] == "state-scrape-wa"
    claim.assert_not_awaited()
    # No count: "scrape this state" means every jurisdiction due, and the workflow decides how
    # many that is. The concurrency window is the API's to supply — a workflow cannot read it
    # itself without breaking replay.
    start.assert_awaited_once()
    assert start.await_args.args[:2] == ("wa", None)


@pytest.mark.unit
def test_claim_registers_and_returns_the_work(client):
    """Synchronous, unlike `/register`: the workflow must know the changesets exist before it
    dispatches anything at them."""
    items = [{"jurisdiction_ocdid": "ocd/x", "changeset_id": "c1", "name": "X", "url": "u"}]
    with patch(
        "routers.api.pipeline_runs.candidate_service.claim_scrape_candidates",
        new_callable=AsyncMock,
        return_value=items,
    ):
        response = client.post(
            "/pipeline_runs/batch/claim", json={"state": "wa", "num_jurisdictions": 1}
        )

    assert response.status_code == 200
    assert response.json()["data"]["jurisdictions"] == items


@pytest.mark.unit
def test_claim_404s_for_an_unknown_state(client):
    with patch(
        "routers.api.pipeline_runs.candidate_service.claim_scrape_candidates",
        new_callable=AsyncMock,
        side_effect=ValueError("No such state: zz"),
    ):
        response = client.post("/pipeline_runs/batch/claim", json={"state": "zz"})

    assert response.status_code == 404
