import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.users import upsert_user


def _make_cursor(returning_row):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchone = AsyncMock(return_value=returning_row)
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
async def test_upsert_user_returns_uuid_string():
    cur = _make_cursor(returning_row=("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",))
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await upsert_user("supabase", "supabase-uuid", "alice@example.com", "Alice")

    assert result == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    cur.execute.assert_awaited_once()
    args, _ = cur.execute.await_args
    assert "INSERT INTO users" in args[0]
    assert "RETURNING id::text" in args[0]
    assert args[1] == ("supabase", "supabase-uuid", "alice@example.com", "Alice")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_upsert_user_does_not_touch_user_roles():
    cur = _make_cursor(returning_row=("any-uuid",))
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await upsert_user("supabase", "id", "x@example.com", None)

    # Only one execute call — no DELETE/INSERT on user_roles
    assert cur.execute.await_count == 1
    args, _ = cur.execute.await_args
    assert "user_roles" not in args[0]
