"""Integration test for set_parent_ocdids against real Postgres.

Run with: mise run tcp-integration
Isolation: sentinel state 'zv', cleaned before/after.
"""

import pytest
import pytest_asyncio

from database.database import get_pool
from database.jurisdictions import set_parent_ocdids

_PLACE_A = "ocd-jurisdiction/country:us/state:zv/place:a/government"
_PLACE_B = "ocd-jurisdiction/country:us/state:zv/place:b/government"
_COUNTY = "ocd-jurisdiction/country:us/state:zv/county:sentinel/government"
_STATE = "ocd-jurisdiction/country:us/state:zv/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zv'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, search_text)
            VALUES (%s, 'zv', 'local', '{}', now(), 'active', '')
            """,
            (ocdid,),
        )
        await conn.commit()


async def _read_parent_ocdids(ocdid):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT parent_ocdids FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writes_parent_ocdids_for_each_jurisdiction():
    await _insert(_PLACE_A)
    await _insert(_PLACE_B)

    await set_parent_ocdids(
        {
            _PLACE_A: [_COUNTY, _STATE],
            _PLACE_B: [_STATE],
        }
    )

    assert await _read_parent_ocdids(_PLACE_A) == [_COUNTY, _STATE]
    assert await _read_parent_ocdids(_PLACE_B) == [_STATE]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_overwrites_not_merges():
    await _insert(_PLACE_A)
    await set_parent_ocdids({_PLACE_A: [_COUNTY, _STATE]})

    await set_parent_ocdids({_PLACE_A: [_STATE]})

    assert await _read_parent_ocdids(_PLACE_A) == [_STATE]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_empty_mapping_is_a_noop():
    await set_parent_ocdids({})
    # No assertion needed beyond not raising — there's nothing to read back.
