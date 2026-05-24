from unittest.mock import AsyncMock, patch

import pytest

from core import change_logs
from shared.utils.statuses import ChangeLogType

REQUEST_ID = "2025-09-25-1a2b"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
USER_ID = "user-123"


# ── record_merge_review ─────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
@patch("core.change_logs.create_change_log", new_callable=AsyncMock)
@patch("core.change_logs.get_people_data_by_request_ids", new_callable=AsyncMock)
@patch("core.change_logs.get_request_jurisdiction", new_callable=AsyncMock)
async def test_record_merge_review_logs_event_then_person_rows(mock_jurisdiction, mock_people, mock_create):
    mock_jurisdiction.return_value = JURISDICTION_OCDID
    mock_people.return_value = {
        REQUEST_ID: {"existing": [], "proposed": [{"id": "p1", "name": "New Person", "office": {"name": "Mayor"}}]}
    }
    await change_logs.record_merge_review(REQUEST_ID, USER_ID)
    logged_types = [call.args[0] for call in mock_create.call_args_list]
    assert logged_types == [ChangeLogType.MERGE_REVIEW, ChangeLogType.ADD_PERSON]


@pytest.mark.unit
@pytest.mark.asyncio
@patch("core.change_logs.create_change_log", new_callable=AsyncMock)
@patch("core.change_logs.get_people_data_by_request_ids", new_callable=AsyncMock)
@patch("core.change_logs.get_request_jurisdiction", new_callable=AsyncMock)
async def test_record_merge_review_skips_when_no_jurisdiction(mock_jurisdiction, mock_people, mock_create):
    mock_jurisdiction.return_value = None
    await change_logs.record_merge_review(REQUEST_ID, USER_ID)
    mock_people.assert_not_called()
    mock_create.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("core.change_logs.create_change_log", new_callable=AsyncMock)
@patch("core.change_logs.get_request_jurisdiction", new_callable=AsyncMock)
async def test_record_merge_review_swallows_errors(mock_jurisdiction, mock_create):
    mock_jurisdiction.side_effect = RuntimeError("db down")
    await change_logs.record_merge_review(REQUEST_ID, USER_ID)  # best-effort: must not raise


# ── record_close_review ──────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
@patch("core.change_logs.create_change_log", new_callable=AsyncMock)
@patch("core.change_logs.get_request_jurisdiction", new_callable=AsyncMock)
async def test_record_close_review_logs_close_event(mock_jurisdiction, mock_create):
    mock_jurisdiction.return_value = JURISDICTION_OCDID
    await change_logs.record_close_review(REQUEST_ID, USER_ID)
    mock_create.assert_awaited_once()
    assert mock_create.call_args.args == (ChangeLogType.CLOSE_REVIEW, USER_ID, JURISDICTION_OCDID, REQUEST_ID)


@pytest.mark.unit
@pytest.mark.asyncio
@patch("core.change_logs.create_change_log", new_callable=AsyncMock)
@patch("core.change_logs.get_request_jurisdiction", new_callable=AsyncMock)
async def test_record_close_review_swallows_errors(mock_jurisdiction, mock_create):
    mock_jurisdiction.return_value = JURISDICTION_OCDID
    mock_create.side_effect = RuntimeError("db down")
    await change_logs.record_close_review(REQUEST_ID, USER_ID)  # best-effort: must not raise
