import pytest
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from database.review_sessions import (
    ReviewSessionStatus,
    create_or_get_review_session,
    end_review_session,
    get_active_review_session,
)

USER_ID = "user-123"
STATE_CODE = "tx"
SESSION_ID = "session-456"

_NOW = datetime.now(timezone.utc)
_RECENT = _NOW - timedelta(minutes=5)   # within idle window
_STALE = _NOW - timedelta(minutes=60)   # outside idle window


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


def _session_row(status=ReviewSessionStatus.IDLE, status_updated_at=None):
    Row = namedtuple("Row", ["status", "status_updated_at"])
    return Row(status=status, status_updated_at=status_updated_at or _STALE)


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
    cur = _make_cursor(fetchone_side_effect=[None])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_active_review_session(USER_ID, STATE_CODE)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_active_review_session_returns_session_when_active():
    Row = namedtuple("Row", ["session_id", "daily_goal", "current_entry_number", "resolved_entry_numbers", "session_pull_request_numbers"])
    row = Row(session_id=SESSION_ID, daily_goal=10, current_entry_number=3, resolved_entry_numbers=[1, 2], session_pull_request_numbers=[101, 102])
    cur = _make_cursor(fetchone_side_effect=[row])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_active_review_session(USER_ID, STATE_CODE)
    assert result is not None
    assert result["session_id"] == SESSION_ID
    assert result["current_entry_number"] == 3


# ── create_or_get_review_session: FSM status checks ──────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_resumes_when_status_active_and_recent():
    """ACTIVE + recent timestamp → preserve queue, no DELETE."""
    cur = _make_cursor(fetchone_side_effect=[
        _session_row(status=ReviewSessionStatus.ACTIVE, status_updated_at=_RECENT),
        _upsert_row(),
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert not any("DELETE" in sql for sql in executed_sql)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_purges_when_status_active_but_stale():
    """ACTIVE but timed out → purge and reset to idle."""
    cur = _make_cursor(fetchone_side_effect=[
        _session_row(status=ReviewSessionStatus.ACTIVE, status_updated_at=_STALE),
        _upsert_row(),
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    all_params = [c.args[1] if len(c.args) > 1 else () for c in cur.execute.call_args_list]
    assert any("DELETE" in sql for sql in executed_sql)
    assert any(ReviewSessionStatus.IDLE in str(p) for p in all_params)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_purges_when_status_idle():
    """IDLE → purge and reset."""
    cur = _make_cursor(fetchone_side_effect=[
        _session_row(status=ReviewSessionStatus.IDLE),
        _upsert_row(),
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert any("DELETE" in sql for sql in executed_sql)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_purges_when_status_complete():
    """COMPLETE → purge and start fresh."""
    cur = _make_cursor(fetchone_side_effect=[
        _session_row(status=ReviewSessionStatus.COMPLETE),
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
    """No existing session → creates fresh, purges (no-op), sets idle."""
    cur = _make_cursor(fetchone_side_effect=[
        None,            # no existing session row
        _upsert_row(),
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    all_params = [c.args[1] if len(c.args) > 1 else () for c in cur.execute.call_args_list]
    assert any(ReviewSessionStatus.IDLE in str(p) for p in all_params)


# ── end_review_session: sets status idle ─────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_end_review_session_sets_status_idle():
    """end_review_session must purge entries AND set status = 'idle'."""
    cur = _make_cursor()
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await end_review_session(SESSION_ID)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    all_params = [c.args[1] if len(c.args) > 1 else () for c in cur.execute.call_args_list]
    assert any("DELETE" in sql for sql in executed_sql)
    assert any(ReviewSessionStatus.IDLE in str(p) for p in all_params)
