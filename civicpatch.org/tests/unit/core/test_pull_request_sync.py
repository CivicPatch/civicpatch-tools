from unittest.mock import AsyncMock, patch

import pytest

from core.pull_request_sync import _get_pr_env, apply_pull_request_status, publish_side_effects
from shared.utils.statuses import PullRequestStatus

REQUEST_ID = "2025-09-25-1a2b"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"


# ── _get_pr_env ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_pr_env_returns_env_from_label():
    labels = [{"name": "env:development"}, {"name": "other-label"}]
    assert _get_pr_env(labels) == "development"


@pytest.mark.unit
def test_get_pr_env_production_label():
    labels = [{"name": "env:production"}]
    assert _get_pr_env(labels) == "production"


@pytest.mark.unit
def test_get_pr_env_defaults_to_production_when_no_env_label():
    labels = [{"name": "other-label"}, {"name": "another"}]
    assert _get_pr_env(labels) == "production"


@pytest.mark.unit
def test_get_pr_env_defaults_to_production_when_empty():
    assert _get_pr_env([]) == "production"


# ── publish_side_effects (people-sync only; credit lives at the endpoints) ────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_merged_matching_env_syncs_people():
    labels = [{"name": "env:production"}]
    with (
        patch(
            "core.pull_request_sync.requests_db.get_request_jurisdiction",
            new_callable=AsyncMock,
            return_value=JURISDICTION_OCDID,
        ),
        patch(
            "core.pull_request_sync.sync_people_by_ocdids",
            new_callable=AsyncMock,
        ) as mock_sync,
        patch(
            "core.pull_request_sync.get_env_vars",
            return_value={"APP_ENVIRONMENT": "production"},
        ),
    ):
        await publish_side_effects(REQUEST_ID, PullRequestStatus.MERGED, labels)
        mock_sync.assert_called_once_with([JURISDICTION_OCDID])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_merged_mismatched_env_skips_sync():
    labels = [{"name": "env:development"}]
    with (
        patch(
            "core.pull_request_sync.requests_db.get_request_jurisdiction",
            new_callable=AsyncMock,
        ) as mock_get_jurisdiction,
        patch(
            "core.pull_request_sync.sync_people_by_ocdids",
            new_callable=AsyncMock,
        ) as mock_sync,
        patch(
            "core.pull_request_sync.get_env_vars",
            return_value={"APP_ENVIRONMENT": "production"},
        ),
    ):
        await publish_side_effects(REQUEST_ID, PullRequestStatus.MERGED, labels)
        mock_get_jurisdiction.assert_not_called()
        mock_sync.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_merged_no_env_label_defaults_to_production_and_syncs():
    labels = []
    with (
        patch(
            "core.pull_request_sync.requests_db.get_request_jurisdiction",
            new_callable=AsyncMock,
            return_value=JURISDICTION_OCDID,
        ),
        patch(
            "core.pull_request_sync.sync_people_by_ocdids",
            new_callable=AsyncMock,
        ) as mock_sync,
        patch(
            "core.pull_request_sync.get_env_vars",
            return_value={"APP_ENVIRONMENT": "production"},
        ),
    ):
        await publish_side_effects(REQUEST_ID, PullRequestStatus.MERGED, labels)
        mock_sync.assert_called_once_with([JURISDICTION_OCDID])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_closed_does_not_sync():
    with patch("core.pull_request_sync.sync_people_by_ocdids", new_callable=AsyncMock) as mock_sync:
        await publish_side_effects(REQUEST_ID, PullRequestStatus.CLOSED, [])
        mock_sync.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_does_not_sync():
    with patch("core.pull_request_sync.sync_people_by_ocdids", new_callable=AsyncMock) as mock_sync:
        await publish_side_effects(REQUEST_ID, PullRequestStatus.OPEN, [])
        mock_sync.assert_not_called()


# ── apply_pull_request_status (funnel: gate side effects on real transition) ───

def _patch_status(previous: str | None, written: bool = True):
    return (
        patch(
            "core.pull_request_sync.pull_requests_db.get_pull_request_status",
            new_callable=AsyncMock,
            return_value=previous,
        ),
        patch(
            "core.pull_request_sync.pull_requests_db.update_pull_request_status",
            new_callable=AsyncMock,
            return_value=written,
        ),
        patch(
            "core.pull_request_sync.publish_side_effects",
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
