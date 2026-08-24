"""Integration test for get_maps_coverage's fresh/scraped/total counts.

Real Postgres: the people pre-agg join + rolling freshness window + parent_ocdids county
expansion. Verifies `fresh` (has-data + recently scraped) sits alongside `scraped` (has-data)
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
# Freshness is a rolling 3-month window, so fixtures are ages rather than fixed dates —
# absolute dates would silently age into the wrong bucket as the calendar moves.
_NOW = datetime.datetime.now(datetime.timezone.utc)
_FRESH_SCRAPE = _NOW - datetime.timedelta(days=30)
_STALE_SCRAPE = _NOW - datetime.timedelta(days=120)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid LIKE 'zz-%'")
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
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
            VALUES (%s, 'zz', 'local', %s, now(), 'active', %s)
            """,
            (ocdid, data, scraped_at),
        )
        if people:
            await cur.execute(
                """
                INSERT INTO people (id, jurisdiction_ocdid, name, updated_at, status)
                VALUES (%s, %s, %s, now(), 'active')
                """,
                (str(uuid.uuid4()), ocdid, "x"),
            )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fresh_sits_alongside_scraped_and_total():
    await _insert("zz-fresh", scraped_at=_FRESH_SCRAPE, people=True)
    await _insert("zz-stale", scraped_at=_STALE_SCRAPE, people=True)
    await _insert("zz-nopeople", scraped_at=_FRESH_SCRAPE, people=False)

    coverage = await get_maps_coverage()

    state = coverage["zz"]["state"]
    assert state["total"] == 3
    assert state["covered"] == 2  # zz-fresh + zz-stale have people
    assert state["covered_fresh"] == 1  # only zz-fresh is since cutoff

    county = coverage["zz"]["counties"][_COUNTY]
    assert county["total"] == 3
    assert county["covered"] == 2
    assert county["covered_fresh"] == 1
