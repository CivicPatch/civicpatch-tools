"""Integration tests for `database.changesets.register_rollback_changeset`.

Real Postgres because what's under test is the FK to `jurisdictions` and the actual
`parent_changeset_id` lookup (`live_roster_changeset`), not just argument plumbing.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.changesets import register_rollback_changeset
from database.database import get_pool
from shared.utils.id_utils import make_id

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_rollback_mint/government"
_USER_EMAIL = "zz-rollback-mint@example.com"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute("DELETE FROM users WHERE provider_user_id = %s", (_USER_EMAIL,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed_user_and_jurisdiction() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'email', %s, %s, 'admins') RETURNING id::text",
            (_USER_EMAIL, _USER_EMAIL, _USER_EMAIL.replace("@", "-")),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    return row[0]


async def test_mints_a_born_published_rollback_changeset():
    user_id = await _seed_user_and_jurisdiction()
    changeset_id = make_id()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await register_rollback_changeset(cur, changeset_id, _OCDID, user_id)
        await conn.commit()

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT kind, published_at, created_by_user_id::text, parent_changeset_id "
            "FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        row = await cur.fetchone()

    assert row is not None
    kind, published_at, created_by_user_id, parent_changeset_id = row
    assert kind == "rollback"
    assert published_at is not None, "born published — a rollback needs no review"
    assert created_by_user_id == user_id
    assert parent_changeset_id is None, "nothing was ever live for this jurisdiction before it"


async def test_returns_and_records_the_changeset_it_rolled_back():
    """The id `register_rollback_changeset` hands back is what the caller needs to know what it
    just rolled back — and it must be the same value the new row's own `parent_changeset_id`
    carries, not a second, possibly-different answer."""
    user_id = await _seed_user_and_jurisdiction()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # Stand in for an already-live changeset — born published, same as a real one would be.
        target_id = make_id()
        await cur.execute(
            "INSERT INTO changesets (id, kind, jurisdiction_ocdid, created_by_user_id, "
            "published_at, created_at) VALUES (%s, 'people_edit', %s, %s, now(), now())",
            (target_id, _OCDID, user_id),
        )
        await conn.commit()

    rollback_id = make_id()
    async with pool.connection() as conn, conn.cursor() as cur:
        rolled_back = await register_rollback_changeset(cur, rollback_id, _OCDID, user_id)
        await conn.commit()

    assert rolled_back == target_id

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT parent_changeset_id::text FROM changesets WHERE id::text = %s",
            (rollback_id,),
        )
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == target_id
