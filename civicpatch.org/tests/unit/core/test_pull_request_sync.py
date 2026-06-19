from unittest.mock import AsyncMock, patch

import pytest

from services.pull_request_sync import apply_pull_request_status, publish_side_effects
from shared.utils.statuses import PullRequestStatus

REQUEST_ID = "2025-09-25-1a2b"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"


# ── publish_side_effects (people-sync only; credit lives at the endpoints) ────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_merged_syncs_people_and_stamps_scraped_at():
    with (
        patch(
            "services.pull_request_sync.requests_db.get_request_jurisdiction",
            new_callable=AsyncMock,
            return_value=JURISDICTION_OCDID,
        ),
        patch(
            "services.pull_request_sync.sync_people_by_ocdids",
            new_callable=AsyncMock,
        ) as mock_sync,
        patch(
            "services.pull_request_sync.jurisdictions_db.stamp_scraped_at",
            new_callable=AsyncMock,
        ) as mock_stamp,
    ):
        await publish_side_effects(REQUEST_ID, PullRequestStatus.MERGED)
        mock_sync.assert_called_once_with([JURISDICTION_OCDID])
        mock_stamp.assert_awaited_once_with(JURISDICTION_OCDID, REQUEST_ID)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_closed_does_not_sync():
    with patch("services.pull_request_sync.sync_people_by_ocdids", new_callable=AsyncMock) as mock_sync:
        await publish_side_effects(REQUEST_ID, PullRequestStatus.CLOSED)
        mock_sync.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_does_not_sync():
    with patch("services.pull_request_sync.sync_people_by_ocdids", new_callable=AsyncMock) as mock_sync:
        await publish_side_effects(REQUEST_ID, PullRequestStatus.OPEN)
        mock_sync.assert_not_called()


# ── apply_pull_request_status (funnel: gate side effects on real transition) ───

def _patch_status(previous: str | None, written: bool = True):
    return (
        patch(
            "services.pull_request_sync.pull_requests_db.get_pull_request_status",
            new_callable=AsyncMock,
            return_value=previous,
        ),
        patch(
            "services.pull_request_sync.pull_requests_db.update_pull_request_status",
            new_callable=AsyncMock,
            return_value=written,
        ),
        patch(
            "services.pull_request_sync.publish_side_effects",
            new_callable=AsyncMock,
        ),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apply_runs_side_effects_on_transition():
    get_status, update, side_effects = _patch_status(previous=PullRequestStatus.OPEN)
    with get_status, update, side_effects as mock_side_effects:
        changed = await apply_pull_request_status(REQUEST_ID, PullRequestStatus.MERGED)
    assert changed is True
    mock_side_effects.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apply_skips_side_effects_when_already_in_status():
    get_status, update, side_effects = _patch_status(previous=PullRequestStatus.MERGED)
    with get_status, update, side_effects as mock_side_effects:
        changed = await apply_pull_request_status(REQUEST_ID, PullRequestStatus.MERGED)
    assert changed is False
    mock_side_effects.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apply_skips_side_effects_when_request_missing():
    get_status, update, side_effects = _patch_status(previous=None, written=False)
    with get_status, update, side_effects as mock_side_effects:
        changed = await apply_pull_request_status(REQUEST_ID, PullRequestStatus.MERGED)
    assert changed is False
    mock_side_effects.assert_not_awaited()
