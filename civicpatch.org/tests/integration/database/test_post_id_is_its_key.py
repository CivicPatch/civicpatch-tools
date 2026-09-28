"""A post's id is its key's hash, in Python and in the database alike (migration 232).

Isolation: sentinel state 'zk', cleaned before and after.
"""

import psycopg
import pytest
import pytest_asyncio

from core.projection.facts import PostKey
from database.database import get_pool
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zk/place:zk_keyed/government"
_DIVISION = "ocd-division/country:us/state:zk/place:zk_keyed"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for table in ("posts", "divisions", "organizations"):
            await cur.execute(f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _organization() -> str:
    await factories.seed_jurisdiction(_OCDID, "zk")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        await cur.execute(
            "INSERT INTO divisions (ocdid, jurisdiction_ocdid) VALUES (%s, %s)", (_DIVISION, _OCDID)
        )
        await conn.commit()
    return organization_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_database_computes_the_same_post_id_as_the_fold():
    organization_id = await _organization()
    key = PostKey(organization_id=organization_id, role_id="mayor", division_ocdid=_DIVISION)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT post_id_of_key(%s, %s, %s)::text",
            (key.organization_id, key.role_id, key.division_ocdid),
        )
        assert await cur.fetchone() == (key.post_id,)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_post_whose_id_is_not_its_key_is_refused():
    """230 renamed divisions without re-keying, and every membership in those towns vanished
    silently at the next publish. The database now refuses the drift itself."""
    organization_id = await _organization()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            await cur.execute(
                "INSERT INTO posts (id, jurisdiction_ocdid, organization_id, role_id, division_ocdid) "
                "VALUES (gen_random_uuid(), %s, %s, 'mayor', %s)",
                (_OCDID, organization_id, _DIVISION),
            )
