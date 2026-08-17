"""Integration tests for get_municipality_rows_for_state (municipalities list page, §8).

Real Postgres: name/officials_count/last_verified_at are plain SQL projections, but status
reuses the same has_people/is_fresh/has_url → classify_map_status path as
get_local_status_for_state (test_local_map_status.py) — this locks the row shape together
against real rows rather than re-proving the classification logic itself.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz' + ocdid prefix 'zz-'; cleaned before/after each test.
"""

import datetime
import json
import uuid

import pytest
import pytest_asyncio

from database.coverage import get_municipality_rows_for_state
from database.database import get_pool

# Freshness is a rolling 90-day window, so fixtures are ages rather than fixed dates —
# absolute dates would silently age into the wrong bucket as the calendar moves.
_FRESH_SCRAPE = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)


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


async def _insert_jurisdiction(ocdid, *, name, url=None, scraped_at=None):
    data = json.dumps({k: v for k, v in {"name": name, "url": url}.items() if v})
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
        await conn.commit()


async def _add_people(ocdid, count):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for _ in range(count):
            await cur.execute(
                """
                INSERT INTO people (id, jurisdiction_ocdid, data, updated_at, status)
                VALUES (%s, %s, %s, now(), 'active')
                """,
                (str(uuid.uuid4()), ocdid, json.dumps({"name": "x"})),
            )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_row_shape_for_fresh_municipality():
    await _insert_jurisdiction(
        "zz-fresh", name="Fresh City", url="https://f", scraped_at=_FRESH_SCRAPE
    )
    await _add_people("zz-fresh", 3)

    rows = await get_municipality_rows_for_state("zz")

    assert rows == [
        {
            "jurisdiction_ocdid": "zz-fresh",
            "name": "Fresh City",
            "status": "fresh",
            "officials_count": 3,
            "last_verified_at": _FRESH_SCRAPE.isoformat(),
        }
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_untracked_municipality_has_no_last_verified_at():
    await _insert_jurisdiction("zz-untracked", name="Untracked Town", url=None, scraped_at=None)

    rows = await get_municipality_rows_for_state("zz")

    assert rows == [
        {
            "jurisdiction_ocdid": "zz-untracked",
            "name": "Untracked Town",
            "status": "untracked",
            "officials_count": 0,
            "last_verified_at": None,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ordered_by_name():
    await _insert_jurisdiction("zz-b", name="Beta Town")
    await _insert_jurisdiction("zz-a", name="Alpha Town")

    rows = await get_municipality_rows_for_state("zz")

    assert [r["name"] for r in rows] == ["Alpha Town", "Beta Town"]
