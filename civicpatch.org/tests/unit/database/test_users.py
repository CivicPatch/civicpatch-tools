import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.users import (
    upsert_user,
    set_user_roles,
    list_users_with_roles,
    get_user_by_id,
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


@pytest.mark.asyncio
@pytest.mark.unit
async def test_set_user_roles_deletes_then_inserts():
    pool, conn = _make_conn_pool()
    with patch("database.users.get_pool", AsyncMock(return_value=pool)):
        await set_user_roles("user-uuid", ["admins", "maintainers"])

    assert conn.execute.await_count == 2
    delete_args, _ = conn.execute.await_args_list[0]
    insert_args, _ = conn.execute.await_args_list[1]
    assert "DELETE FROM user_roles" in delete_args[0]
    assert delete_args[1] == ("user-uuid",)
    assert "INSERT INTO user_roles" in insert_args[0]
    assert insert_args[1] == ("user-uuid", ["admins", "maintainers"])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_set_user_roles_empty_skips_insert():
    pool, conn = _make_conn_pool()
    with patch("database.users.get_pool", AsyncMock(return_value=pool)):
        await set_user_roles("user-uuid", [])

    assert conn.execute.await_count == 1
    args, _ = conn.execute.await_args_list[0]
    assert "DELETE FROM user_roles" in args[0]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_users_with_roles_empty():
    cur = _make_cursor(returning_rows=[])
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await list_users_with_roles()

    assert result == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_users_with_roles_populated():
    rows = [
        ("uuid-1", "alice@example.com", "Alice", "supabase", "sb-1", ["admins"]),
        ("uuid-2", "bob@example.com", None, "supabase", "sb-2", []),
    ]
    cur = _make_cursor(returning_rows=rows)
    with patch("database.users.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await list_users_with_roles()

    assert result == [
        {
            "id": "uuid-1",
            "email": "alice@example.com",
            "display_name": "Alice",
            "provider": "supabase",
            "provider_user_id": "sb-1",
            "roles": ["admins"],
        },
        {
            "id": "uuid-2",
            "email": "bob@example.com",
            "display_name": None,
            "provider": "supabase",
            "provider_user_id": "sb-2",
            "roles": [],
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
