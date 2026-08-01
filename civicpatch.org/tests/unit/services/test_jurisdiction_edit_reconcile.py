from unittest.mock import AsyncMock, patch

import pytest

from services.jurisdiction_edit_reconcile import reconcile_landed_jurisdiction_edits
from shared.utils.statuses import PullRequestStatus


@pytest.mark.unit
@pytest.mark.asyncio
async def test_marks_landed_edits_merged_and_leaves_pending_alone():
    """However it landed — our merge, a squash, or someone else's identical edit —
    the projection is the evidence. Edits still absent are left open, since pending
    and rejected are indistinguishable from here."""
    edits = [
        {"request_id": "landed", "patch": {"url": "https://new.gov"}, "current": {"url": "https://new.gov"}},
        {"request_id": "pending", "patch": {"url": "https://new.gov"}, "current": {"url": "https://old.gov"}},
    ]
    with (
        patch(
            "services.jurisdiction_edit_reconcile.requests_db.get_open_jurisdiction_edits",
            new_callable=AsyncMock, return_value=edits,
        ),
        patch(
            "services.jurisdiction_edit_reconcile.apply_pull_request_status",
            new_callable=AsyncMock,
        ) as mock_apply,
    ):
        count = await reconcile_landed_jurisdiction_edits()

    assert count == 1
    mock_apply.assert_awaited_once_with("landed", PullRequestStatus.MERGED)
