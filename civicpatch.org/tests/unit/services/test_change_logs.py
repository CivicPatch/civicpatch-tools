from unittest.mock import AsyncMock, patch

import pytest

from services import change_logs
from shared.utils.statuses import ChangeLogType

REQUEST_ID = "2025-09-25-1a2b"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
USER_ID = "user-123"


# ── record_publish (event-only) ───────────────────

@pytest.mark.unit
# ── record_manual_edits (the publish-time diff) ──────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.change_logs.create_change_log", new_callable=AsyncMock)
async def test_record_manual_edits_logs_diff_rows(mock_create):
    before = [{"id": "p1", "name": "Jane", "office": {"name": "Mayor"}}]
    after = [{"id": "p1", "name": "Jane Doe", "office": {"name": "Mayor"}}]
    await change_logs.record_manual_edits(REQUEST_ID, JURISDICTION_OCDID, USER_ID, before, after)
    mock_create.assert_awaited_once()
    args = mock_create.call_args.args
    assert args[0] == ChangeLogType.EDIT_PERSON
    assert args[1:4] == (USER_ID, JURISDICTION_OCDID, REQUEST_ID)


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.change_logs.create_change_log", new_callable=AsyncMock)
async def test_record_manual_edits_no_diff_logs_nothing(mock_create):
    people = [{"id": "p1", "name": "Jane", "office": {"name": "Mayor"}}]
    await change_logs.record_manual_edits(REQUEST_ID, JURISDICTION_OCDID, USER_ID, people, people)
    mock_create.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.change_logs.create_change_log", new_callable=AsyncMock)
async def test_record_manual_edits_swallows_errors(mock_create):
    mock_create.side_effect = RuntimeError("db down")
    before = []
    after = [{"id": "p1", "name": "Jane", "office": {"name": "Mayor"}}]
    await change_logs.record_manual_edits(REQUEST_ID, JURISDICTION_OCDID, USER_ID, before, after)  # must not raise
