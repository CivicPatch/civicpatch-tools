from unittest.mock import AsyncMock, patch

import pytest

from services import change_logs
from shared.utils.statuses import ChangeLogType

CHANGESET_ID = "2025-09-25-1a2b"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
USER_ID = "user-123"


# ── record_manual_edits (the publish-time diff) ──────────────────────────────

# All three patch `create_change_logs`, the batch writer. They patched `create_change_log`
# until 2026-09-06, when the loop became one `executemany` — a connection was being checked
# out of a pool of twenty *per changed field*.


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.change_logs.create_change_logs", new_callable=AsyncMock)
async def test_record_manual_edits_logs_diff_rows(mock_create):
    before = [{"id": "p1", "name": "Jane", "office": {"name": "Mayor"}}]
    after = [{"id": "p1", "name": "Jane Doe", "office": {"name": "Mayor"}}]
    await change_logs.record_manual_edits(CHANGESET_ID, JURISDICTION_OCDID, USER_ID, before, after)
    mock_create.assert_awaited_once()
    entries, *rest = mock_create.call_args.args
    assert [change_type for change_type, _payload in entries] == [ChangeLogType.EDIT_PERSON]
    assert tuple(rest) == (USER_ID, JURISDICTION_OCDID, CHANGESET_ID)


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.change_logs.create_change_logs", new_callable=AsyncMock)
async def test_record_manual_edits_no_diff_logs_nothing(mock_create):
    """An unchanged roster yields no entries. The writer is still called and returns early on
    an empty batch, so this asserts the rows rather than the call."""
    people = [{"id": "p1", "name": "Jane", "office": {"name": "Mayor"}}]
    await change_logs.record_manual_edits(CHANGESET_ID, JURISDICTION_OCDID, USER_ID, people, people)
    assert mock_create.call_args.args[0] == []


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.change_logs.create_change_logs", new_callable=AsyncMock)
async def test_record_manual_edits_swallows_errors(mock_create):
    mock_create.side_effect = RuntimeError("db down")
    before = []
    after = [{"id": "p1", "name": "Jane", "office": {"name": "Mayor"}}]
    await change_logs.record_manual_edits(CHANGESET_ID, JURISDICTION_OCDID, USER_ID, before, after)  # must not raise
