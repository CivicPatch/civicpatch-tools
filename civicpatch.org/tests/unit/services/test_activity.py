"""`write_person_changes`: the activity writer publish calls once its own write has landed.

The `record_manual_edits` / `diff_manual_edits` tests went on 2026-09-24. They verified that
publishing diffed the roster itself and logged the result. That path no longer exists: its only
caller was `edit_published`, deleted with step 9, and the diff is now the fold's own
`core/activity.changes_from_diff` (pinned in `test_changes_from_diff.py`), which publish hands
straight to the writer below. What is left to test here is the forwarding and the swallowing.
"""

from unittest.mock import AsyncMock, patch

import pytest

from schemas.activity import Change, FieldChange, PersonChange
from schemas.claims import EntityType
from services import activity
from shared.utils.statuses import ActivityType

CHANGESET_ID = "2025-09-25-1a2b"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
USER_ID = "user-123"


def _renamed() -> PersonChange:
    return PersonChange(
        type=ActivityType.EDIT_PERSON,
        payload=Change(
            entity_type=EntityType.PERSON,
            entity_id="p1",
            subject="Jane Doe",
            fields=[FieldChange(field="name", before="Jane", after="Jane Doe")],
        ),
    )


# Patches `create_activity_rows`, the batch writer. It patched `create_activity_row` until
# 2026-09-06, when the loop became one `executemany` — a connection was being checked out of a
# pool of twenty *per changed field*.


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.activity.create_activity_rows", new_callable=AsyncMock)
async def test_write_person_changes_forwards_type_and_payload(mock_create):
    """This verified the forwarding of what `diff_manual_edits` produced. It now verifies the
    forwarding of a `PersonChange` built here, because that function is deleted and publish
    supplies the changes itself."""
    change = _renamed()

    await activity.write_person_changes(
        CHANGESET_ID, JURISDICTION_OCDID, USER_ID, [change]
    )

    mock_create.assert_awaited_once_with(
        [(ActivityType.EDIT_PERSON, change.payload)],
        USER_ID,
        JURISDICTION_OCDID,
        CHANGESET_ID,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.activity.create_activity_rows", new_callable=AsyncMock)
async def test_write_person_changes_swallows_errors(mock_create):
    mock_create.side_effect = RuntimeError("db down")
    await activity.write_person_changes(CHANGESET_ID, JURISDICTION_OCDID, USER_ID, [])  # must not raise
