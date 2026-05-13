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
async def test_get_active_review_session_filters_by_ended_at():
    # Active resume must only return sessions that have not been ended.
    cur = _make_cursor(fetchone_side_effect=[None])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await get_active_review_session(USER_ID)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert any("ended_at IS NULL" in sql for sql in executed_sql)


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
    # Was: ACTIVE + recent → no DELETE; the same row was returned via ON CONFLICT DO UPDATE.
    # Now: existing non-ended session with is_active=True → UPDATE daily_goal on the same row,
    # no DELETE and no INSERT. Same behavioral guarantee: a recent session is preserved
    # without purging the in-flight queue.
    Existing = namedtuple("Existing", ["id", "is_active"])
    cur = _make_cursor(fetchone_side_effect=[
        Existing(id=SESSION_ID, is_active=True),  # existing non-ended, active
        _upsert_row(),                             # UPDATE ... RETURNING
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert not any("DELETE" in sql for sql in executed_sql)
    assert not any("INSERT INTO review_sessions" in sql for sql in executed_sql)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_auto_ends_and_inserts_when_session_is_stale():
    # Was: ACTIVE-but-stale → DELETE entries + UPDATE same row (set IDLE).
    # Now: stale non-ended session → purge entries, set ended_at on the old row, then
    # INSERT a brand-new session row. The user gets a fresh session id with entry_number
    # sequence starting at 1 — this is the core fix for the End-session bug.
    Existing = namedtuple("Existing", ["id", "is_active"])
    cur = _make_cursor(fetchone_side_effect=[
        Existing(id=SESSION_ID, is_active=False),  # existing non-ended, stale
        _upsert_row(),                              # INSERT ... RETURNING
        _next_entry_row(),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert any("DELETE FROM review_session_entries" in sql for sql in executed_sql)
    assert any("ended_at = NOW()" in sql for sql in executed_sql)
    assert any("INSERT INTO review_sessions" in sql for sql in executed_sql)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_or_get_inserts_new_row_when_no_prior_session():
    # Was: no existing session → DELETE (no-op) + UPSERT.
    # Now: no non-ended session found → directly INSERT a new row. No purge, no auto-end.
    # Returned next_entry_number must be 1 for a fresh session row.
    cur = _make_cursor(fetchone_side_effect=[
        None,                  # no existing non-ended session
        _upsert_row(),         # INSERT ... RETURNING
        _next_entry_row(1),
    ])
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await create_or_get_review_session(USER_ID, STATE_CODE, daily_goal=10)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert not any("DELETE" in sql for sql in executed_sql)
    assert not any("ended_at = NOW()" in sql for sql in executed_sql)
    assert any("INSERT INTO review_sessions" in sql for sql in executed_sql)
    assert result["next_entry_number"] == 1


# ── end_review_session ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_end_review_session_sets_ended_at_and_purges_queue():
    # Was: end_session purges entries AND resets current_entry_number + reviewed_ocdids
    # on the same row. Now: end_session purges entries AND sets ended_at = NOW(), so
    # the next create_or_get inserts a fresh row with a fresh entry_number sequence.
    # The soft-reset of current_entry_number is gone — that was the source of the
    # "End then Start lands back at page 71" bug.
    cur = _make_cursor()
    with patch("database.review_sessions.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await end_review_session(SESSION_ID)

    executed_sql = [str(c.args[0]) for c in cur.execute.call_args_list]

    assert any("DELETE FROM review_session_entries" in sql for sql in executed_sql)
    assert any("ended_at = NOW()" in sql for sql in executed_sql)
    assert not any("current_entry_number = 1" in sql for sql in executed_sql)
