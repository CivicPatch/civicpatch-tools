"""Integration tests for users-table behavior that's load-bearing for the
username sign-up flow.

Three behaviors get exercised against real Postgres here that the unit tests
structurally can't cover:

  - `touch_last_login` must not touch `username` on a re-login. The unit test
    only verifies its SQL doesn't mention the column; this test verifies the
    actual user-row's value is preserved across a re-login.
  - The UNIQUE constraint on `users.username` (from migration 096, carried
    forward by 192) must actually reject a second insert with the same value.
    `create_user` itself can't collide (its username is always its own,
    freshly generated id), so this now exercises `set_username` — the only
    path a user-chosen name reaches the database.
  - The CHECK constraint from 193 must actually reject an illegal character
    at the database, independent of the Pydantic `Username` validator that
    normally catches it first — a defense against anything that bypasses that
    layer (a bug in it, a future direct-SQL writer, a bad backfill). Also
    exercised via `set_username` for the same reason.

Run with:
  mise run tcp-integration

Isolation: tests use a sentinel `provider_user_id` prefix that cannot collide
with seeded users, and `clean_users` wipes those rows before/after each test.
"""
import pytest
import pytest_asyncio
from psycopg.errors import CheckViolation, UniqueViolation

from database.database import get_pool
from database.users import (
    create_user,
    set_username,
    touch_last_login,
)

_PROVIDER = "supabase"
_SENTINEL_PREFIX = "test-username-"


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


async def _read_username(user_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT username FROM users WHERE id = %s", (user_id,)
        )
        row = await cur.fetchone()
        assert row is not None, f"user {user_id} not found"
        return row[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_touch_last_login_preserves_existing_username():
    # First login: the account is created with its id as a placeholder username.
    user_id = await create_user(_PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com")
    assert await _read_username(user_id) == user_id

    # User finishes onboarding (or later changes it via /settings).
    await set_username(user_id, "orchard-fox")
    assert await _read_username(user_id) == "orchard-fox"

    # Subsequent login (same provider/id) → touch_last_login. It must NOT touch
    # the user's actual handle. This is the load-bearing behavior the sign-up
    # flow depends on; if it regresses, every re-login wipes users' handles.
    await touch_last_login(_PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com")

    assert await _read_username(user_id) == "orchard-fox"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unique_constraint_rejects_duplicate_username():
    # Two accounts, then both try to claim the same chosen username — second must fail.
    alice_id = await create_user(_PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com")
    bob_id = await create_user(_PROVIDER, _SENTINEL_PREFIX + "bob", "bob@example.com")
    await set_username(alice_id, "apple-witch")

    with pytest.raises(UniqueViolation):
        await set_username(bob_id, "apple-witch")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_check_constraint_rejects_an_illegal_character():
    # A space is the exact shape of the pre-193 data this migration existed to fix.
    carol_id = await create_user(_PROVIDER, _SENTINEL_PREFIX + "carol", "carol@example.com")

    with pytest.raises(CheckViolation):
        await set_username(carol_id, "apple witch")
