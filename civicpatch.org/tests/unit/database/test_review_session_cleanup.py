import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.review_session_navigation import cleanup_stale_review_session_entries


def _make_pool_with_rowcount(rowcount: int):
    cur = AsyncMock()
    cur.__aenter__ = AsyncMock(return_value=cur)
    cur.__aexit__ = AsyncMock(return_value=False)
    cur.rowcount = rowcount
    cur.execute = AsyncMock()

    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cur)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = AsyncMock()
    pool.connection = MagicMock(return_value=conn)
    return pool, cur


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cleanup_returns_zero_when_nothing_stale():
    # Was: returned {"entries_deleted": 0, "sessions_idled": 0}.
    # Now: returned {"entries_deleted": 0} — sessions_idled key removed with status column.
    pool, _ = _make_pool_with_rowcount(0)
    with patch("database.review_session_navigation.get_pool", new_callable=AsyncMock, return_value=pool):
        result = await cleanup_stale_review_session_entries()

    assert result == {"entries_deleted": 0}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cleanup_returns_correct_entry_count():
    # Was: returned both entries_deleted and sessions_idled counts.
    # Now: returns only entries_deleted — no session status to update.
    pool, _ = _make_pool_with_rowcount(4)
    with patch("database.review_session_navigation.get_pool", new_callable=AsyncMock, return_value=pool):
        result = await cleanup_stale_review_session_entries()

    assert result == {"entries_deleted": 4}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cleanup_runs_single_delete():
    # Was: ran DELETE then UPDATE (two SQL statements).
    # Now: runs only DELETE — sessions_idled step removed with status column.
    sql_verbs = []
    cur = AsyncMock()
    cur.__aenter__ = AsyncMock(return_value=cur)
    cur.__aexit__ = AsyncMock(return_value=False)
    cur.rowcount = 0

    async def capture(sql, *args, **kwargs):
        sql_verbs.append(sql.strip().split()[0].upper())

    cur.execute = capture

    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cur)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = AsyncMock()
    pool.connection = MagicMock(return_value=conn)

    with patch("database.review_session_navigation.get_pool", new_callable=AsyncMock, return_value=pool):
        await cleanup_stale_review_session_entries()

    assert sql_verbs == ["DELETE"], (
        "Cleanup must run exactly one DELETE — the UPDATE sessions step was removed with status column"
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cleanup_delete_checks_session_updated_at():
    # Was: DELETE filtered by status_updated_at IS NULL OR status_updated_at < cutoff.
    # Now: DELETE filters by updated_at < cutoff — column renamed, IS NULL check gone.
    # Verifies that the DELETE joins review_sessions and uses the new column name.
    sqls = []
    cur = AsyncMock()
    cur.__aenter__ = AsyncMock(return_value=cur)
    cur.__aexit__ = AsyncMock(return_value=False)
    cur.rowcount = 0

    async def capture(sql, *args, **kwargs):
        sqls.append(sql)

    cur.execute = capture

    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cur)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = AsyncMock()
    pool.connection = MagicMock(return_value=conn)

    with patch("database.review_session_navigation.get_pool", new_callable=AsyncMock, return_value=pool):
        await cleanup_stale_review_session_entries()

    delete_sql = sqls[0]
    assert "USING review_sessions" in delete_sql
    assert "updated_at" in delete_sql
    assert "status_updated_at" not in delete_sql
