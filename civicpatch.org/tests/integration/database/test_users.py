"""Integration tests for users-table behavior that's load-bearing for the
display_name picker flow.

Two behaviors get exercised against real Postgres here that the unit tests
structurally can't cover:

  - `upsert_user` must not touch `display_name` on conflict. The unit test
    only verifies the SQL doesn't contain the string 'display_name'; this
    test verifies the actual user-row's value is preserved across a re-login.
  - The UNIQUE constraint on `users.display_name` (from migration 096) must
    actually reject a second insert with the same value.

Run with:
  mise run tcp-integration

Isolation: tests use a sentinel `provider_user_id` prefix that cannot collide
with seeded users, and `clean_users` wipes those rows before/after each test.
"""
import pytest
import pytest_asyncio
from psycopg.errors import UniqueViolation

from database.database import get_pool
from database.users import (
    set_user_display_name,
    upsert_user,
)

_PROVIDER = "supabase"
_SENTINEL_PREFIX = "test-display-name-"


async def _wipe_sentinel_users():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM users WHERE provider_user_id LIKE %s",
            (_SENTINEL_PREFIX + "%",),
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_users():
    await _wipe_sentinel_users()
    yield
    await _wipe_sentinel_users()


async def _read_display_name(user_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT display_name FROM users WHERE id = %s", (user_id,)
        )
        row = await cur.fetchone()
        assert row is not None, f"user {user_id} not found"
        return row[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upsert_user_preserves_existing_display_name_on_reconflict():
    # First login: create user with no display_name (the new normal — OAuth
    # never supplies one).
    user_id = await upsert_user(_PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com")
    assert await _read_display_name(user_id) is None

    # User picks a display_name via /settings.
    await set_user_display_name(user_id, "apple-witch")
    assert await _read_display_name(user_id) == "apple-witch"

    # Subsequent login (same provider/id) → upsert_user is called again. It
    # must NOT clobber the user-chosen display_name. This is the load-bearing
    # behavior the picker depends on; if it regresses, every re-login wipes
    # users' handles back to NULL and the activity feed renders "Anonymous".
    same_id = await upsert_user(_PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com")

    assert same_id == user_id
    assert await _read_display_name(user_id) == "apple-witch"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unique_constraint_rejects_duplicate_display_name():
    # Two users, both pick the same display_name — second one must fail.
    alice_id = await upsert_user(_PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com")
    bob_id = await upsert_user(_PROVIDER, _SENTINEL_PREFIX + "bob", "bob@example.com")

    await set_user_display_name(alice_id, "apple-witch")

    with pytest.raises(UniqueViolation):
        await set_user_display_name(bob_id, "apple-witch")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unique_constraint_allows_multiple_null_display_names():
    # The constraint must keep treating NULLs as distinct (Postgres default).
    # Otherwise existing users without a picked handle would block each
    # other from logging in at all.
    await upsert_user(_PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com")
    await upsert_user(_PROVIDER, _SENTINEL_PREFIX + "bob", "bob@example.com")
    # Both have NULL display_name; reaching this line means no UniqueViolation
    # was raised.
