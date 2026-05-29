import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.users import (
    upsert_user,
    set_user_role,
    list_users,
    get_user_by_id,
    display_name_in_use,
    set_user_display_name,
)


def _make_cursor(returning_row=None, returning_rows=None):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchone = AsyncMock(return_value=returning_row)
    cur.fetchall = AsyncMock(return_value=returning_rows or [])
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


def _make_conn_pool():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = AsyncMock()
    pool.connection = MagicMock(return_value=conn)
    return pool, conn


@pytest.mark.asyncio
@pytest.mark.unit
async def test_upsert_user_returns_uuid_string():
    cur = _make_cursor(returning_row=("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",))
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await upsert_user("supabase", "supabase-uuid", "alice@example.com")

    assert result == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    cur.execute.assert_awaited_once()
    args, _ = cur.execute.await_args
    assert "INSERT INTO users" in args[0]
    assert "RETURNING id::text" in args[0]
    assert args[1] == ("supabase", "supabase-uuid", "alice@example.com")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_upsert_user_does_not_touch_user_roles():
    cur = _make_cursor(returning_row=("any-uuid",))
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await upsert_user("supabase", "id", "x@example.com")

    # Only one execute call — no role mutation
    assert cur.execute.await_count == 1
    args, _ = cur.execute.await_args
    assert "user_roles" not in args[0]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_upsert_user_does_not_write_display_name():
    # display_name belongs to the user, set via /settings — upsert_user must
    # never insert or update it (no clobbering on re-login, no OAuth import).
    cur = _make_cursor(returning_row=("any-uuid",))
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await upsert_user("supabase", "id", "x@example.com")

    args, _ = cur.execute.await_args
    sql = args[0]
    assert "display_name" not in sql


@pytest.mark.asyncio
@pytest.mark.unit
async def test_display_name_in_use_true_when_row_returned():
    cur = _make_cursor(returning_row=(1,))
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await display_name_in_use("apple-witch")

    assert result is True
    args, _ = cur.execute.await_args
    assert "WHERE display_name = %s" in args[0]
    assert args[1] == ("apple-witch",)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_display_name_in_use_false_when_no_row():
    cur = _make_cursor(returning_row=None)
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await display_name_in_use("free-name")

    assert result is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_set_user_display_name_runs_update():
    pool, conn = _make_conn_pool()
    with patch("database.users.get_pool", AsyncMock(return_value=pool)):
        await set_user_display_name("user-uuid", "apple-witch")

    assert conn.execute.await_count == 1
    args, _ = conn.execute.await_args_list[0]
    assert "UPDATE users SET display_name = %s WHERE id = %s" in args[0]
    assert args[1] == ("apple-witch", "user-uuid")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_set_user_role_updates_users_table():
    pool, conn = _make_conn_pool()
    with patch("database.users.get_pool", AsyncMock(return_value=pool)):
        await set_user_role("user-uuid", "admins")

    assert conn.execute.await_count == 1
    args, _ = conn.execute.await_args_list[0]
    assert "UPDATE users SET role" in args[0]
    assert args[1] == ("admins", "user-uuid")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_set_user_role_with_default_resets_level():
    pool, conn = _make_conn_pool()
    with patch("database.users.get_pool", AsyncMock(return_value=pool)):
        await set_user_role("user-uuid", "default")

    assert conn.execute.await_count == 1
    args, _ = conn.execute.await_args_list[0]
    assert args[1] == ("default", "user-uuid")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_users_empty():
    cur = _make_cursor(returning_rows=[])
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await list_users()

    assert result == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_users_populated():
    from datetime import datetime, timezone
    login_ts = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    rows = [
        ("uuid-1", "alice@example.com", "Alice", "supabase", "sb-1", "admins", login_ts),
        ("uuid-2", "bob@example.com", None, "supabase", "sb-2", "default", None),
    ]
    cur = _make_cursor(returning_rows=rows)
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await list_users()

    assert result == [
        {
            "id": "uuid-1",
            "email": "alice@example.com",
            "display_name": "Alice",
            "provider": "supabase",
            "provider_user_id": "sb-1",
            "role": "admins",
            "last_login_at": login_ts.isoformat(),
        },
        {
            "id": "uuid-2",
            "email": "bob@example.com",
            "display_name": None,
            "provider": "supabase",
            "provider_user_id": "sb-2",
            "role": "default",
            "last_login_at": None,
        },
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_by_id_found():
    row = ("uuid-1", "supabase", "sb-1", "alice@example.com", "Alice")
    cur = _make_cursor(returning_row=row)
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_user_by_id("uuid-1")

    assert result == {
        "id": "uuid-1",
        "provider": "supabase",
        "provider_user_id": "sb-1",
        "email": "alice@example.com",
        "display_name": "Alice",
    }


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_by_id_not_found():
    cur = _make_cursor(returning_row=None)
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_user_by_id("missing-uuid")

    assert result is None
