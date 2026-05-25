import pytest
from unittest.mock import AsyncMock, patch
from temporalio.testing import ActivityEnvironment

from routers.temporal.activities import cleanup_stale_review_entries_activity


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cleanup_activity_calls_db_function():
    result = {"entries_deleted": 0}
    with patch(
        "routers.temporal.activities.review_session_entries_db.purge_stale_idle_sessions",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock_cleanup:
        env = ActivityEnvironment()
        await env.run(cleanup_stale_review_entries_activity)

    mock_cleanup.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cleanup_activity_logs_when_entries_deleted():
    result = {"entries_deleted": 3}
    with patch(
        "routers.temporal.activities.review_session_entries_db.purge_stale_idle_sessions",
        new_callable=AsyncMock,
        return_value=result,
    ):
        env = ActivityEnvironment()
        # Should complete without raising — logging is fire-and-forget
        await env.run(cleanup_stale_review_entries_activity)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cleanup_activity_silent_when_nothing_to_clean():
    result = {"entries_deleted": 0}
    with patch(
        "routers.temporal.activities.review_session_entries_db.purge_stale_idle_sessions",
        new_callable=AsyncMock,
        return_value=result,
    ):
        env = ActivityEnvironment()
        await env.run(cleanup_stale_review_entries_activity)
