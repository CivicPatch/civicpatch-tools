from unittest.mock import AsyncMock, patch

import pytest

from core.pull_request_sync import _get_pr_env, handle_pr_status_side_effects
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


# ── handle_pr_status_side_effects ─────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_merged_matching_env_syncs_people():
    labels = [{"name": "env:production"}]
    with (
        patch(
            "core.pull_request_sync.review_session_entries_db.resolve_review_session_entries_by_request_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
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
        await handle_pr_status_side_effects(REQUEST_ID, PullRequestStatus.MERGED, labels)
        mock_resolve.assert_called_once_with(REQUEST_ID)
        mock_sync.assert_called_once_with([JURISDICTION_OCDID])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_merged_mismatched_env_skips_sync():
    labels = [{"name": "env:development"}]
    with (
        patch(
            "core.pull_request_sync.review_session_entries_db.resolve_review_session_entries_by_request_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
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
        await handle_pr_status_side_effects(REQUEST_ID, PullRequestStatus.MERGED, labels)
        mock_resolve.assert_called_once_with(REQUEST_ID)
        mock_get_jurisdiction.assert_not_called()
        mock_sync.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_merged_no_env_label_defaults_to_production_and_syncs():
    labels = []
    with (
        patch(
            "core.pull_request_sync.review_session_entries_db.resolve_review_session_entries_by_request_id",
            new_callable=AsyncMock,
        ),
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
        await handle_pr_status_side_effects(REQUEST_ID, PullRequestStatus.MERGED, labels)
        mock_sync.assert_called_once_with([JURISDICTION_OCDID])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_closed_resolves_review_sessions_no_sync():
    labels = [{"name": "env:production"}]
    with (
        patch(
            "core.pull_request_sync.review_session_entries_db.resolve_review_session_entries_by_request_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "core.pull_request_sync.sync_people_by_ocdids",
            new_callable=AsyncMock,
        ) as mock_sync,
        patch(
            "core.pull_request_sync.get_env_vars",
            return_value={"APP_ENVIRONMENT": "production"},
        ),
    ):
        await handle_pr_status_side_effects(REQUEST_ID, PullRequestStatus.CLOSED, labels)
        mock_resolve.assert_called_once_with(REQUEST_ID)
        mock_sync.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_status_no_side_effects():
    labels = [{"name": "env:production"}]
    with (
        patch(
            "core.pull_request_sync.review_session_entries_db.resolve_review_session_entries_by_request_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "core.pull_request_sync.sync_people_by_ocdids",
            new_callable=AsyncMock,
        ) as mock_sync,
        patch(
            "core.pull_request_sync.get_env_vars",
            return_value={"APP_ENVIRONMENT": "production"},
        ),
    ):
        await handle_pr_status_side_effects(REQUEST_ID, PullRequestStatus.OPEN, labels)
        mock_resolve.assert_not_called()
        mock_sync.assert_not_called()
