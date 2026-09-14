"""Integration test for get_all_states_geoid_lookup against real Postgres.

Run with: mise run tcp-integration
Isolation: sentinel states 'zx'/'zy', cleaned before/after.
"""

import json

import pytest
import pytest_asyncio

from core.map_enrichment import GeoidEntry
from database.database import get_pool
from database.jurisdictions import get_all_states_geoid_lookup

_STATE_ZX = "ocd-jurisdiction/country:us/state:zx/government"
_STATE_ZY = "ocd-jurisdiction/country:us/state:zy/government"
_COUNTY_ZX = "ocd-jurisdiction/country:us/state:zx/county:sentinel/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdictions WHERE state IN ('zx', 'zy')")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid, *, state, level, geoid, name, status="active"):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, search_text)
            VALUES (%s, %s, %s, %s, now(), %s, '')
            """,
            (ocdid, state, level, json.dumps({"geoid": geoid, "name": name}), status),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_covers_every_active_state_not_just_one():
    await _insert(_STATE_ZX, state="zx", level="state", geoid="91", name="Zx")
    await _insert(_STATE_ZY, state="zy", level="state", geoid="92", name="Zy")

    lookup = await get_all_states_geoid_lookup()

    assert lookup["91"] == GeoidEntry(_STATE_ZX, "Zx")
    assert lookup["92"] == GeoidEntry(_STATE_ZY, "Zy")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_excludes_non_state_levels():
    await _insert(_STATE_ZX, state="zx", level="state", geoid="91", name="Zx")
    await _insert(_COUNTY_ZX, state="zx", level="counties", geoid="91001", name="Sentinel County")

    lookup = await get_all_states_geoid_lookup()

    assert "91001" not in lookup


@pytest.mark.asyncio
@pytest.mark.integration
async def test_excludes_inactive_state():
    await _insert(_STATE_ZX, state="zx", level="state", geoid="91", name="Zx", status="inactive")

    lookup = await get_all_states_geoid_lookup()

    assert "91" not in lookup
