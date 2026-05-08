import pytest
from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock, patch, call

from database.review_sessions import get_active_review_session, create_or_get_review_session

USER_ID = "user-123"
STATE_CODE = "tx"
SESSION_ID = "session-456"


def _make_cursor(fetchone_side_effect=None, fetchall_return=None):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    if fetchone_side_effect is not None:
        cur.fetchone = AsyncMock(side_effect=fetchone_side_effect)
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


# ── get_active_review_session ─────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_active_review_session_returns_none_when_no_session():
    cur = _make_cursor(fetchone_side_effect=[None])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_active_review_session(USER_ID, STATE_CODE)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_active_review_session_returns_session_when_active():
    Row = namedtuple("Row", ["session_id", "daily_goal", "current_entry_number"])
    row = Row(session_id=SESSION_ID, daily_goal=10, current_entry_number=3)
    cur = _make_cursor(fetchone_side_effect=[row])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_active_review_session(USER_ID, STATE_CODE)
    assert result is not None
    assert result["session_id"] == SESSION_ID
    assert result["current_entry_number"] == 3


# ── create_or_get_review_session: idle check ──────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_does_not_wipe_entries_when_session_is_active():
    """When session has recent activity, non-resolved entries must be preserved."""
    ActiveRow = namedtuple("ActiveRow", ["is_active"])
    SessionRow = namedtuple("SessionRow", ["id", "state_code", "daily_goal", "created_at"])
    from datetime import datetime, timezone
    session_row = SessionRow(
        id=SESSION_ID, state_code=STATE_CODE, daily_goal=10,
        created_at=datetime.now(timezone.utc),
    )

    cur = _make_cursor(fetchone_side_effect=[
        ActiveRow(is_active=True),         # idle check: session IS active
        session_row,                       # INSERT ON CONFLICT RETURNING
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert not any("DELETE" in sql for sql in executed_sql)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_wipes_entries_when_session_is_idle():
    """When session has been idle, non-resolved entries must be wiped."""
    ActiveRow = namedtuple("ActiveRow", ["is_active"])
    SessionRow = namedtuple("SessionRow", ["id", "state_code", "daily_goal", "created_at"])
    from datetime import datetime, timezone
    session_row = SessionRow(
        id=SESSION_ID, state_code=STATE_CODE, daily_goal=10,
        created_at=datetime.now(timezone.utc),
    )

    cur = _make_cursor(fetchone_side_effect=[
        ActiveRow(is_active=False),        # idle check: session is idle
        session_row,                       # INSERT ON CONFLICT RETURNING
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert any("DELETE" in sql for sql in executed_sql)
