import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from temporalio.testing import ActivityEnvironment

from routers.temporal.sink_activities import (
    _ACTIVITY_FEED_WATERMARK_KEY,
    write_activity_feed_activity,
)


def _patch(watermark, rows):
    return (
        patch(
            "routers.temporal.sink_activities.redis_store.get",
            new_callable=AsyncMock,
            return_value=watermark,
        ),
        patch(
            "routers.temporal.sink_activities.redis_store.set",
            new_callable=AsyncMock,
        ),
        patch(
            "routers.temporal.sink_activities.activity_db.get_live_activity_since",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "routers.temporal.sink_activities.pubsub_service.publish",
            new_callable=AsyncMock,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_no_watermark_falls_back_to_the_initial_lookback():
    get, set_, since, publish = _patch(None, [])
    with get, set_, since as mock_since, publish:
        await ActivityEnvironment().run(write_activity_feed_activity)

    passed_since = mock_since.call_args.args[0]
    assert passed_since < datetime.now(timezone.utc)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_an_existing_watermark_is_used_as_the_cursor():
    watermark = datetime(2026, 9, 11, 11, 59, 0, tzinfo=timezone.utc)
    get, set_, since, publish = _patch(watermark.isoformat(), [])
    with get, set_, since as mock_since, publish:
        await ActivityEnvironment().run(write_activity_feed_activity)

    mock_since.assert_awaited_once_with(watermark)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rows_are_grouped_by_type_and_published_once_per_group():
    # Three, not two: below core.activity.MIN_GROUP_SIZE, pipeline_run_start would stay
    # ungrouped too — see core/test_activity.py for the threshold itself.
    now = datetime.now(timezone.utc)
    rows = [
        {"type": "pipeline_run_start", "jurisdiction_ocdid": "a", "created_at": now},
        {"type": "pipeline_run_start", "jurisdiction_ocdid": "b", "created_at": now},
        {"type": "pipeline_run_start", "jurisdiction_ocdid": "c", "created_at": now},
        {"type": "publish_review", "jurisdiction_ocdid": "d", "created_at": now},
    ]
    get, set_, since, publish = _patch(None, rows)
    with get, set_, since, publish as mock_publish:
        await ActivityEnvironment().run(write_activity_feed_activity)

    assert mock_publish.await_count == 2
    channels = {call.args[0] for call in mock_publish.await_args_list}
    assert channels == {"activity"}
    payloads = [json.loads(call.args[1]) for call in mock_publish.await_args_list]
    assert {"type": "pipeline_run_start", "count": 3} in payloads
    assert {"type": "publish_review", "count": 1} in payloads


@pytest.mark.asyncio
@pytest.mark.unit
async def test_an_empty_sweep_publishes_nothing_but_still_advances_the_watermark():
    get, set_, since, publish = _patch(None, [])
    with get, set_ as mock_set, since, publish as mock_publish:
        await ActivityEnvironment().run(write_activity_feed_activity)

    mock_publish.assert_not_awaited()
    mock_set.assert_awaited_once()
    key, value = mock_set.call_args.args
    assert key == _ACTIVITY_FEED_WATERMARK_KEY
    # A valid, recent watermark — the exact instant isn't asserted since the activity reads the
    # real clock; freezing it would test the mock, not the behavior.
    assert datetime.fromisoformat(value) <= datetime.now(timezone.utc)
