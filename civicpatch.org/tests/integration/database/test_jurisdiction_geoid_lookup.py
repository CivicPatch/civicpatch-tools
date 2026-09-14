"""Integration test for get_geoid_lookup against real Postgres.

Run with: mise run tcp-integration
Isolation: sentinel state 'zu', its own state code so another suite's fixtures cannot leak
into get_geoid_lookup()'s whole-state result; cleaned before/after.
"""

import json

import pytest
import pytest_asyncio

from core.map_enrichment import GeoidEntry
from database.database import get_pool
from database.jurisdictions import get_geoid_lookup

_STATE_OCDID = "ocd-jurisdiction/country:us/state:zu/government"
_COUNTY_OCDID = "ocd-jurisdiction/country:us/state:zu/county:sentinel/government"
_PLACE_OCDID = "ocd-jurisdiction/country:us/state:zu/place:zutown/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zu'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid, *, level, geoid, name="Sentinel", status="active"):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, search_text)
            VALUES (%s, 'zu', %s, %s, now(), %s, '')
            """,
            (ocdid, level, json.dumps({"geoid": geoid, "name": name}), status),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_returns_geoid_to_entry_across_levels():
    await _insert(_STATE_OCDID, level="state", geoid="99", name="Zu")
    await _insert(_COUNTY_OCDID, level="counties", geoid="99999", name="Sentinel County")
    await _insert(_PLACE_OCDID, level="local", geoid="9912345", name="Zutown city")

    lookup = await get_geoid_lookup("zu")

    assert lookup == {
        "99": GeoidEntry(_STATE_OCDID, "Zu"),
        "99999": GeoidEntry(_COUNTY_OCDID, "Sentinel County"),
        "9912345": GeoidEntry(_PLACE_OCDID, "Zutown city"),
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
            (other_state_ocdid, json.dumps({"geoid": "9912345", "name": "Other"})),
        )
        await conn.commit()

    try:
        lookup = await get_geoid_lookup("zu")
        assert lookup == {"9912345": GeoidEntry(_PLACE_OCDID, "Sentinel")}
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
    no_geoid_ocdid = "ocd-jurisdiction/country:us/state:zu/place:nogeoid/government"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, search_text)
            VALUES (%s, 'zu', 'local', '{}', now(), 'active', '')
            """,
            (no_geoid_ocdid,),
        )
        await conn.commit()

    lookup = await get_geoid_lookup("zu")

    assert lookup == {}
