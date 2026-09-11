"""Integration tests for users-table behavior that's load-bearing for the
username sign-up flow.

Three behaviors get exercised against real Postgres here that the unit tests
structurally can't cover:

  - `upsert_user` must not touch `username` on conflict. The unit test only
    verifies the SQL's DO UPDATE SET doesn't mention it; this test verifies
    the actual user-row's value is preserved across a re-login.
  - The UNIQUE constraint on `users.username` (from migration 096, carried
    forward by 192) must actually reject a second insert with the same value.
  - The CHECK constraint from 193 must actually reject an illegal character
    at the database, independent of the Pydantic `Username` validator that
    normally catches it first — a defense against anything that bypasses that
    layer (a bug in it, a future direct-SQL writer, a bad backfill).

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
    set_username,
    upsert_user,
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
async def test_upsert_user_preserves_existing_username_on_reconflict():
    # First login: create the account with the username chosen at sign-up.
    user_id = await upsert_user(
        _PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com", "apple-witch"
    )
    assert await _read_username(user_id) == "apple-witch"

    # User later changes it via /settings.
    await set_username(user_id, "orchard-fox")
    assert await _read_username(user_id) == "orchard-fox"

    # Subsequent login (same provider/id) → upsert_user is called again, with
    # whatever the login form happened to be given. It must NOT clobber the
    # user's actual handle. This is the load-bearing behavior the sign-up flow
    # depends on; if it regresses, every re-login wipes users' handles.
    same_id = await upsert_user(
        _PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com", "ignored-name"
    )

    assert same_id == user_id
    assert await _read_username(user_id) == "orchard-fox"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unique_constraint_rejects_duplicate_username():
    # Two accounts, both created with the same chosen username — second must fail.
    await upsert_user(_PROVIDER, _SENTINEL_PREFIX + "alice", "alice@example.com", "apple-witch")

    with pytest.raises(UniqueViolation):
        await upsert_user(_PROVIDER, _SENTINEL_PREFIX + "bob", "bob@example.com", "apple-witch")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_check_constraint_rejects_an_illegal_character():
    # A space is the exact shape of the pre-193 data this migration existed to fix.
    with pytest.raises(CheckViolation):
        await upsert_user(
            _PROVIDER, _SENTINEL_PREFIX + "carol", "carol@example.com", "apple witch"
        )
