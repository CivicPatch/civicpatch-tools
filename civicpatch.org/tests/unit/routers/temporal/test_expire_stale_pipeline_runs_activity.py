import pytest
from unittest.mock import AsyncMock, patch
from temporalio.testing import ActivityEnvironment

from routers.temporal.activities import (
    _STALE_RUN_ISSUE_DETAIL,
    _STALE_RUN_ISSUE_TYPE,
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
    expire, upsert = _patch(["req-a", "req-b"])
    with expire, upsert as mock_upsert:
        await ActivityEnvironment().run(expire_stale_pipeline_runs_activity)

    # each crashed run gets a blocking issue so it isn't silently re-queued
    assert mock_upsert.await_count == 2
    mock_upsert.assert_any_await("req-a", _STALE_RUN_ISSUE_TYPE, [_STALE_RUN_ISSUE_DETAIL])
    mock_upsert.assert_any_await("req-b", _STALE_RUN_ISSUE_TYPE, [_STALE_RUN_ISSUE_DETAIL])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_raises_no_issue_when_nothing_expired():
    expire, upsert = _patch([])
    with expire, upsert as mock_upsert:
        await ActivityEnvironment().run(expire_stale_pipeline_runs_activity)

    mock_upsert.assert_not_awaited()
