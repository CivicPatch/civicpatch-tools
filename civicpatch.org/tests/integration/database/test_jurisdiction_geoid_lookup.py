"""Integration test for get_geoid_to_ocdid_lookup against real Postgres.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz', cleaned before/after.
"""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.jurisdictions import get_geoid_to_ocdid_lookup

_STATE_OCDID = "ocd-jurisdiction/country:us/state:zz/government"
_COUNTY_OCDID = "ocd-jurisdiction/country:us/state:zz/county:sentinel/government"
_PLACE_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zztown/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid, *, level, geoid, status="active"):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, search_text)
            VALUES (%s, 'zz', %s, %s, now(), %s, '')
            """,
            (ocdid, level, json.dumps({"geoid": geoid}), status),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_returns_geoid_to_ocdid_across_levels():
    await _insert(_STATE_OCDID, level="state", geoid="99")
    await _insert(_COUNTY_OCDID, level="counties", geoid="99999")
    await _insert(_PLACE_OCDID, level="local", geoid="9912345")

    lookup = await get_geoid_to_ocdid_lookup("zz")

    assert lookup == {
        "99": _STATE_OCDID,
        "99999": _COUNTY_OCDID,
        "9912345": _PLACE_OCDID,
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_excludes_other_states():
    await _insert(_PLACE_OCDID, level="local", geoid="9912345")
    other_state_ocdid = "ocd-jurisdiction/country:us/state:yy/place:other/government"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, search_text)
            VALUES (%s, 'yy', 'local', %s, now(), 'active', '')
            """,
            (other_state_ocdid, json.dumps({"geoid": "9912345"})),
        )
        await conn.commit()

    try:
        lookup = await get_geoid_to_ocdid_lookup("zz")
        assert lookup == {"9912345": _PLACE_OCDID}
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s",
                (other_state_ocdid,),
            )
            await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_excludes_inactive_and_missing_geoid():
    await _insert(_PLACE_OCDID, level="local", geoid="9912345", status="inactive")
    no_geoid_ocdid = "ocd-jurisdiction/country:us/state:zz/place:nogeoid/government"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, search_text)
            VALUES (%s, 'zz', 'local', '{}', now(), 'active', '')
            """,
            (no_geoid_ocdid,),
        )
        await conn.commit()

    lookup = await get_geoid_to_ocdid_lookup("zz")

    assert lookup == {}
