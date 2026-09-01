import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.issues import create_user_reported_issue, get_user_reported_issues_for_request
from shared.utils.statuses import PipelineIssueStatus, PipelineIssueType


def _make_cursor(fetchone_return=None, fetchall_return=None):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchone = AsyncMock(return_value=fetchone_return)
    cur.fetchall = AsyncMock(return_value=fetchall_return or [])
    cur.__aenter__ = AsyncMock(return_value=cur)
    cur.__aexit__ = AsyncMock(return_value=False)
    return cur


def _make_pool(cursor):
    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cursor)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = AsyncMock()
    pool.connection = MagicMock(return_value=conn)
    return pool


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_user_reported_issue_inserts_pending_row_and_returns_id():
    cur = _make_cursor(("issue-id-123",))
    with patch("database.issues.get_pool", AsyncMock(return_value=_make_pool(cur))):
        issue_id = await create_user_reported_issue(
            changeset_id="req-1",
            title="Review flag: Oakland",
            body="Something looks wrong.",
            github_issue_url="https://github.com/org/open-data/issues/9",
            github_issue_number=9,
            reported_by_user_id="user-1",
        )

    assert issue_id == "issue-id-123"
    cur.execute.assert_awaited_once()
    _, params = cur.execute.call_args[0]
    issue_type, issue_key, changeset_ids, data, status = params
    assert issue_type == PipelineIssueType.USER_REPORTED
    assert isinstance(issue_key, str) and issue_key
    assert changeset_ids == ["req-1"]
    assert status == PipelineIssueStatus.PENDING
    assert json.loads(data) == {
        "title": "Review flag: Oakland",
        "body": "Something looks wrong.",
        "github_issue_url": "https://github.com/org/open-data/issues/9",
        "github_issue_number": 9,
        "reported_by_user_id": "user-1",
    }


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_user_reported_issue_uses_distinct_keys_per_call():
    cur1 = _make_cursor(("issue-1",))
    cur2 = _make_cursor(("issue-2",))
    with patch(
        "database.issues.get_pool",
        AsyncMock(side_effect=[_make_pool(cur1), _make_pool(cur2)]),
    ):
        await create_user_reported_issue("req-1", "t", "b", "url", 1, "user-1")
        await create_user_reported_issue("req-1", "t", "b", "url", 1, "user-1")

    key1 = cur1.execute.call_args[0][1][1]
    key2 = cur2.execute.call_args[0][1][1]
    assert key1 != key2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_reported_issues_for_request_shapes_rows():
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row = (
        "issue-1",
        {
            "title": "Review flag: Oakland",
            "body": "Something looks wrong.",
            "github_issue_url": "https://github.com/org/open-data/issues/9",
            "github_issue_number": 9,
            "reported_by_user_id": "user-1",
        },
        PipelineIssueStatus.PENDING,
        created_at,
    )
    cur = _make_cursor(fetchall_return=[row])
    with patch("database.issues.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_user_reported_issues_for_request("req-1")

    assert result == [
        {
            "id": "issue-1",
            "title": "Review flag: Oakland",
            "github_issue_url": "https://github.com/org/open-data/issues/9",
            "github_issue_number": 9,
            "status": PipelineIssueStatus.PENDING,
            "created_at": created_at.isoformat(),
        }
    ]
    cur.execute.assert_awaited_once()
    _, params = cur.execute.call_args[0]
    assert params == (PipelineIssueType.USER_REPORTED, "req-1")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_reported_issues_for_request_returns_empty_list_when_none():
    cur = _make_cursor(fetchall_return=[])
    with patch("database.issues.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_user_reported_issues_for_request("req-missing")

    assert result == []
