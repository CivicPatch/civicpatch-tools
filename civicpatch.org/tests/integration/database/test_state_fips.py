"""Integration test for get_state_fips against real Postgres.

Run with: mise run tcp-integration
Isolation: sentinel state 'zw', cleaned before/after.
"""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.jurisdictions import get_state_fips


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zw'")
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
            VALUES (%s, 'zw', %s, %s, now(), %s, '')
            """,
            (ocdid, level, json.dumps({"geoid": geoid}), status),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_returns_the_states_own_geoid():
    await _insert(
        "ocd-jurisdiction/country:us/state:zw/government", level="state", geoid="99"
    )
    await _insert(
        "ocd-jurisdiction/country:us/state:zw/county:sentinel/government",
        level="counties",
        geoid="99999",
    )

    assert await get_state_fips("zw") == "99"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_returns_none_for_unknown_state():
    assert await get_state_fips("zw") is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ignores_inactive_state_row():
    await _insert(
        "ocd-jurisdiction/country:us/state:zw/government",
        level="state",
        geoid="99",
        status="inactive",
    )

    assert await get_state_fips("zw") is None
