import pytest
from unittest.mock import AsyncMock, patch
from temporalio.testing import ActivityEnvironment

from schemas.pipeline_runs import ExpiredRun
from shared.utils.statuses import PipelineIssueType

from routers.temporal.activities import (
    _STALE_RUN_ISSUE_DETAIL,
    expire_stale_pipeline_runs_activity,
)


def _patch(expired):
    return (
        patch(
            "routers.temporal.activities.pipeline_runs_db.expire_stale_pipeline_runs",
            new_callable=AsyncMock,
            return_value=expired,
        ),
        patch(
            "routers.temporal.activities.upsert_issue",
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

    # each crashed run gets a blocking issue so it isn't silently re-queued
    assert mock_upsert.await_count == 2
    mock_upsert.assert_any_await("req-a", PipelineIssueType.PIPELINE_ERROR, [_STALE_RUN_ISSUE_DETAIL])
    mock_upsert.assert_any_await("req-b", PipelineIssueType.PIPELINE_ERROR, [_STALE_RUN_ISSUE_DETAIL])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_run_that_proposed_nothing_is_keyed_on_the_run():
    """No proposal to key on, and the issue still has to be visible — the issues page renders
    `issue_key` bare when it resolves to no changeset."""
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
