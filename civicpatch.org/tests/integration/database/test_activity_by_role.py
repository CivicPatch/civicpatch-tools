"""Integration test for get_activity_for_roles' role filter.

Real Postgres: `roles=None` must drop the `WHERE u.role = ANY(%s)` clause entirely rather than
matching an empty list, which would silently return zero rows.

Run with: mise run tcp-integration
Isolation: sentinel users below, deleted before/after — activity cascades on user delete.
"""

import pytest
import pytest_asyncio

from database.activity import get_activity_for_roles
from database.database import get_pool

_DEFAULT_EMAIL = "zz-default@example.com"
_ADMIN_EMAIL = "zz-admin@example.com"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM users WHERE email IN (%s, %s)", (_DEFAULT_EMAIL, _ADMIN_EMAIL))


async def _seed() -> tuple[str, str]:
    """Returns the two seeded activity ids (default author, admin author)."""
    pool = await get_pool()
    ids = {}
    async with pool.connection() as conn, conn.cursor() as cur:
        for email, role in ((_DEFAULT_EMAIL, "default"), (_ADMIN_EMAIL, "admins")):
            await cur.execute(
                "INSERT INTO users (email, provider, provider_user_id, role) "
                "VALUES (%s, 'email', %s, %s) RETURNING id::text",
                (email, email, role),
            )
            row = await cur.fetchone()
            assert row is not None
            user_id = row[0]
            await cur.execute(
                "INSERT INTO activity (type, user_id) VALUES ('add_person', %s) RETURNING id::text",
                (user_id,),
            )
            log_row = await cur.fetchone()
            assert log_row is not None
            ids[role] = log_row[0]
    return ids["default"], ids["admins"]


@pytest_asyncio.fixture
async def seeded_ids():
    await _wipe()
    ids = await _seed()
    yield ids
    await _wipe()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_none_returns_rows_from_every_role(seeded_ids):
    default_id, admin_id = seeded_ids
    # A large enough page to reach both sentinel rows regardless of what else is in the table.
    _, rows = await get_activity_for_roles(None, limit=1000, offset=0)
    ids = {row["id"] for row in rows}
    assert {default_id, admin_id} <= ids


@pytest.mark.asyncio
@pytest.mark.integration
async def test_role_list_narrows_to_those_roles(seeded_ids):
    default_id, admin_id = seeded_ids
    _, rows = await get_activity_for_roles(["default"], limit=1000, offset=0)
    ids = {row["id"] for row in rows}
    assert default_id in ids
    assert admin_id not in ids
    assert all(row["author_role"] == "default" for row in rows)
