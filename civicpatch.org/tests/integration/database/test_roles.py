"""Integration tests for the role taxonomy SQL layer (database.roles).

Roles are written only by the open-data config sync, so these seed rows with SQL and pin what the
reads return. Every test confines its rows to sentinel ids under _SENTINEL_ID_PATTERN.

Run with:
  mise run tcp-integration
"""
import pytest
import pytest_asyncio

from database.database import get_pool
from database.roles import get_roles

_SENTINEL_ID_PATTERN = "zz-test-%"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # role_aliases cascades on role delete
        await cur.execute("DELETE FROM roles WHERE id LIKE %s", (_SENTINEL_ID_PATTERN,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_roles():
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_candidate_alias_is_stored_but_not_returned():
    """Approval is the whole reason role_aliases is a table: an unapproved alias
    must survive in storage and stay invisible to the matcher."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO roles (id, label, status, is_unique) VALUES ('zz-test-mayor', 'ZZ Test Mayor', 'active', true)"
        )
        await cur.execute(
            "INSERT INTO role_aliases (role_id, label, status) VALUES"
            " ('zz-test-mayor', 'zz mayor', 'active'), ('zz-test-mayor', 'zz unapproved', 'candidate')"
        )
        await conn.commit()

    mayor = next(r for r in await get_roles() if r.id == "zz-test-mayor")
    assert mayor.aliases == ["zz mayor"]

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT count(*) FROM role_aliases WHERE role_id = %s", ("zz-test-mayor",))
        assert (await cur.fetchone())[0] == 2, "the candidate must still be stored"
