import pytest
from collections import namedtuple
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from database.review_sessions import create_or_get_review_session, get_active_review_session
from database.review_sessions import end_review_session

USER_ID = "user-123"
STATE_CODE = "tx"
SESSION_ID = "session-456"

_NOW = datetime.now(timezone.utc)


def _make_cursor(fetchone_side_effect=None):
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


def _upsert_row():
    Row = namedtuple("Row", ["id", "state_code", "daily_goal", "created_at"])
    return Row(id=SESSION_ID, state_code=STATE_CODE, daily_goal=10, created_at=_NOW)


def _next_entry_row(n=1):
    Row = namedtuple("Row", ["next_entry_number"])
    return Row(next_entry_number=n)


# ── get_active_review_session ─────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_active_review_session_returns_none_when_no_session():
    # Was: returns None when status filter finds nothing.
    # Now: returns None when updated_at filter finds nothing. Same observable outcome.
    cur = _make_cursor(fetchone_side_effect=[None])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_active_review_session(USER_ID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_active_review_session_returns_session_when_active():
    # Was: returns session when status == ACTIVE and timestamp is recent.
    # Now: returns session when updated_at is within the idle window. Same outcome.
    Row = namedtuple("Row", ["session_id", "state_code", "daily_goal", "current_entry_number", "resolved_entry_numbers", "session_pull_request_numbers"])
    row = Row(session_id=SESSION_ID, state_code=STATE_CODE, daily_goal=10, current_entry_number=3, resolved_entry_numbers=[1, 2], session_pull_request_numbers=[101, 102])
    cur = _make_cursor(fetchone_side_effect=[row])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_active_review_session(USER_ID)
    assert result is not None
    assert result["session_id"] == SESSION_ID
    assert result["current_entry_number"] == 3


# ── create_or_get_review_session ──────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_resumes_when_session_is_recent():
    # Was: ACTIVE + recent status_updated_at → no DELETE.
    # Now: updated_at within idle window (fetchone returns a row) → no DELETE.
    # Same behavior: recent session preserved without purging the queue.
    cur = _make_cursor(fetchone_side_effect=[
        object(),       # active-check query returns a row → is_active = True
        _upsert_row(),
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert not any("DELETE" in sql for sql in executed_sql)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_purges_when_session_is_stale():
    # Was: ACTIVE but status_updated_at is stale → DELETE + set IDLE.
    # Now: updated_at outside idle window (fetchone returns None) → DELETE.
    # Status column gone; purge behavior unchanged.
    cur = _make_cursor(fetchone_side_effect=[
        None,           # active-check query returns nothing → is_active = False
        _upsert_row(),
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert any("DELETE" in sql for sql in executed_sql)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_purges_when_no_prior_session():
    # Was: no existing session → purge (no-op) + set IDLE.
    # Now: no active session found → purge (no-op). No status to set.
    cur = _make_cursor(fetchone_side_effect=[
        None,           # active-check returns nothing
        _upsert_row(),
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert any("DELETE" in sql for sql in executed_sql)


# ── end_review_session ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_end_review_session_purges_entries_and_resets_session():
    # Was: end_session purges entries AND sets status = 'idle'.
    # Now: end_session purges entries AND resets current_entry_number + reviewed_ocdids.
    #      Status column removed; reset behavior unchanged.
    cur = _make_cursor()
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await end_review_session(SESSION_ID)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    all_params = [str(c.args[1]) if len(c.args) > 1 else "" for c in cur.execute.call_args_list]

    assert any("DELETE" in sql for sql in executed_sql)
    assert any("reviewed_ocdids" in sql for sql in executed_sql)
    assert not any("idle" in p for p in all_params), (
        "end_review_session must not write a status value — status column was removed"
    )
