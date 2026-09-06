"""Settling a run's reported status.

These moved here verbatim from `tests/unit/routers/test_pipeline_runs.py` when the logic left
the router for `services/`. What they assert is unchanged.
"""

from unittest.mock import AsyncMock, patch

import pytest
from services import pipeline_runs as run_lifecycle
from shared.utils.statuses import DismissalReason

TEST_CHANGESET_ID = "test-request-id-123"
TEST_OCDID = "ocd-jurisdiction/country:us/state:wa/place:buckley/government"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apply_pipeline_run_status_publishes_when_jurisdiction_provided():
    with (
        patch("services.pipeline_runs.update_pipeline_run_status", new_callable=AsyncMock) as mock_update,
        patch("services.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock) as mock_publish,
    ):
        await run_lifecycle.apply_pipeline_run_status(TEST_CHANGESET_ID, "running", 50, "ocd-division/country:us/state:ca/place:oakland")

        mock_update.assert_awaited_once_with(run_id=TEST_CHANGESET_ID, status="running", progress=50)
        mock_publish.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apply_pipeline_run_status_skips_publish_when_no_jurisdiction():
    with (
        patch("services.pipeline_runs.update_pipeline_run_status", new_callable=AsyncMock),
        patch("services.pipeline_runs.get_pipeline_run", new_callable=AsyncMock, return_value=None),
        patch("database.database.get_pool", new_callable=AsyncMock),
        patch("services.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock) as mock_publish,
    ):
        await run_lifecycle.apply_pipeline_run_status(TEST_CHANGESET_ID, "running", 50, None)

        mock_publish.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["CANCELLED", "ERROR"])
async def test_a_run_that_ended_without_a_roster_settles_its_request(status):
    """Both leave nothing to review, so both have to stop counting as pending work — the
    jurisdiction page lists pending requests and `peopleEditBlockers` disables editing from the
    same set, so a failure left a permanent blocker behind."""
    with (
        patch("services.pipeline_runs.dismiss_changeset", new_callable=AsyncMock) as dismiss,
        patch(
            "services.pipeline_runs.supersede_prior_jurisdiction_issues",
            new_callable=AsyncMock,
        ),
    ):
        await run_lifecycle.finalize_pipeline_run(TEST_CHANGESET_ID, status, TEST_OCDID)

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
        patch("services.pipeline_runs.dismiss_changeset", new_callable=AsyncMock) as dismiss,
        patch(
            "services.pipeline_runs.supersede_prior_jurisdiction_issues",
            new_callable=AsyncMock,
        ),
    ):
        await run_lifecycle.finalize_pipeline_run(TEST_CHANGESET_ID, status, TEST_OCDID)

    dismiss.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["CANCELLED", "ERROR"])
async def test_a_run_that_minted_nothing_settles_nothing(status):
    """A run that died before ingest has no proposal to dismiss and replaced nothing, so both
    branches are skipped rather than matching zero rows. The attempt is still counted — the
    changesets page reads runs, not only proposals."""
    with (
        patch("services.pipeline_runs.dismiss_changeset", new_callable=AsyncMock) as dismiss,
        patch(
            "services.pipeline_runs.supersede_prior_jurisdiction_issues",
            new_callable=AsyncMock,
        ) as supersede,
    ):
        await run_lifecycle.finalize_pipeline_run(None, status, TEST_OCDID)

    dismiss.assert_not_awaited()
    supersede.assert_not_awaited()
