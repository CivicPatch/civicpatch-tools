from unittest.mock import AsyncMock, patch

import pytest

from services import pull_request_merge
from shared.utils.statuses import PipelineIssueType


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.pull_request_merge.issues_db.upsert_issue", new_callable=AsyncMock)
@patch("services.pull_request_merge.pull_requests_db.get_stuck_merges", new_callable=AsyncMock)
async def test_reconcile_raises_merge_failed_for_each_stuck_pr(mock_get_stuck, mock_upsert):
    mock_get_stuck.return_value = [
        {"request_id": "req-1", "pr_number": 40, "url": "https://github.com/x/y/pull/40"},
        {"request_id": "req-2", "pr_number": 41, "url": "https://github.com/x/y/pull/41"},
    ]

    await pull_request_merge.reconcile_stuck_merges(15)

    assert mock_upsert.await_count == 2
    request_id, issue_type, _ = mock_upsert.await_args_list[0].args
    assert request_id == "req-1"
    assert issue_type == PipelineIssueType.MERGE_FAILED


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.pull_request_merge.issues_db.upsert_issue", new_callable=AsyncMock)
@patch("services.pull_request_merge.pull_requests_db.get_stuck_merges", new_callable=AsyncMock)
async def test_reconcile_raises_nothing_when_no_stuck_merges(mock_get_stuck, mock_upsert):
    mock_get_stuck.return_value = []

    await pull_request_merge.reconcile_stuck_merges(15)

    mock_upsert.assert_not_awaited()
