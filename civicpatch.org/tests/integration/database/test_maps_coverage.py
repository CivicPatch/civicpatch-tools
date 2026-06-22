"""Integration test for get_maps_coverage's fresh/scraped/total counts.

Real Postgres: the people pre-agg join + state_configs cutoff + parent_ocdids county
expansion. Verifies `fresh` (has-data + since cutoff) sits alongside `scraped` (has-data)
at both state and county level, so the map can shade by staleness.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz' + ocdid prefix, cleaned before/after.
"""

import datetime
import json
import uuid

import pytest
import pytest_asyncio

from database.coverage import get_maps_coverage
from database.database import get_pool

_COUNTY = "ocd-jurisdiction/country:us/state:zz/county:testcounty/government"
_CUTOFF = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
_AFTER_CUTOFF = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
_BEFORE_CUTOFF = datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid LIKE 'zz-%'")
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        await cur.execute("DELETE FROM state_configs WHERE state = 'zz'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid, *, scraped_at, people):
    data = json.dumps({"url": "https://x", "parent_ocdids": [_COUNTY]})
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, scraped_at)
            VALUES (%s, 'zz', 'local', %s, now(), 'current', %s)
            """,
            (ocdid, data, scraped_at),
        )
        if people:
            await cur.execute(
                """
                INSERT INTO people (id, jurisdiction_ocdid, data, updated_at, status)
                VALUES (%s, %s, %s, now(), 'current')
                """,
                (str(uuid.uuid4()), ocdid, json.dumps({"name": "x"})),
            )
        await cur.execute(
            """
            INSERT INTO state_configs (state, min_scraped_at) VALUES ('zz', %s)
            ON CONFLICT (state) DO UPDATE SET min_scraped_at = EXCLUDED.min_scraped_at
            """,
            (_CUTOFF,),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fresh_sits_alongside_scraped_and_total():
    await _insert("zz-fresh", scraped_at=_AFTER_CUTOFF, people=True)
    await _insert("zz-stale", scraped_at=_BEFORE_CUTOFF, people=True)
    await _insert("zz-nopeople", scraped_at=_AFTER_CUTOFF, people=False)

    coverage = await get_maps_coverage()

    state = coverage["zz"]["state"]
    assert state["total"] == 3
    assert state["covered"] == 2  # zz-fresh + zz-stale have people
    assert state["covered_fresh"] == 1  # only zz-fresh is since cutoff

    county = coverage["zz"]["counties"][_COUNTY]
    assert county["total"] == 3
    assert county["covered"] == 2
    assert county["covered_fresh"] == 1
