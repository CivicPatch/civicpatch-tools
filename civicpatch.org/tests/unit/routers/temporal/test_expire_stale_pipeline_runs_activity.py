import pytest
from unittest.mock import AsyncMock, patch
from temporalio.testing import ActivityEnvironment

from schemas.pipeline_runs import ExpiredRun
from shared.utils.statuses import PipelineIssueType

from routers.temporal.expiry_activities import (
    _STALE_RUN_ISSUE_DETAIL,
    expire_stale_pipeline_runs_activity,
)


def _patch(expired):
    return (
        patch(
            "routers.temporal.expiry_activities.pipeline_runs_db.expire_stale_pipeline_runs",
            new_callable=AsyncMock,
            return_value=expired,
        ),
        patch(
            "routers.temporal.expiry_activities.upsert_issue",
            new_callable=AsyncMock,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_raises_an_issue_per_expired_run():
    expire, upsert = _patch([
        ExpiredRun(pipeline_run_id="run-a", changeset_id="req-a"),
        ExpiredRun(pipeline_run_id="run-b", changeset_id="req-b"),
    ])
    with expire, upsert as mock_upsert:
        await ActivityEnvironment().run(expire_stale_pipeline_runs_activity)

    # Keyed on the run, not on whatever it happened to propose. It used to prefer the
    # changeset id when there was one, which is how one table came to hold two kinds of id.
    assert mock_upsert.await_count == 2
    mock_upsert.assert_any_await("run-a", PipelineIssueType.PIPELINE_ERROR, [_STALE_RUN_ISSUE_DETAIL])
    mock_upsert.assert_any_await("run-b", PipelineIssueType.PIPELINE_ERROR, [_STALE_RUN_ISSUE_DETAIL])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_run_that_proposed_nothing_is_keyed_on_the_run():
    """The case that used to be special and no longer is: every run is keyed the same way, so a
    scrape that died before ingest needs no fallback. The jurisdiction comes off the run, which
    is what makes it visible on a state-filtered issues page at all."""
    expire, upsert = _patch([ExpiredRun(pipeline_run_id="run-a", changeset_id=None)])
    with expire, upsert as mock_upsert:
        await ActivityEnvironment().run(expire_stale_pipeline_runs_activity)

    mock_upsert.assert_awaited_once_with(
        "run-a", PipelineIssueType.PIPELINE_ERROR, [_STALE_RUN_ISSUE_DETAIL]
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_raises_no_issue_when_nothing_expired():
    expire, upsert = _patch([])
    with expire, upsert as mock_upsert:
        await ActivityEnvironment().run(expire_stale_pipeline_runs_activity)

    mock_upsert.assert_not_awaited()
