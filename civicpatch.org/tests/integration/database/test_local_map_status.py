"""Integration tests for get_local_status_for_state (map colors).

Real Postgres: the freshness/has-people/has-url flags are SQL; the FRESH/STALE/GAP/
UNTRACKED call is the pure core.coverage.classify_map_status. This locks the two
together against real rows.

Run with: mise run tcp-integration

Isolation: sentinel state 'zz' + ocdid prefix 'zz-'; cleaned before/after each test.
"""

import datetime
import json
import uuid

import pytest
import pytest_asyncio

from core.coverage import MapStatus
from database.coverage import get_local_status_for_state
from database.database import get_pool

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


async def _insert_jurisdiction(ocdid, *, url=None, scraped_at=None):
    data = json.dumps({"url": url} if url else {})
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
        await cur.execute(
            """
            INSERT INTO state_configs (state, min_scraped_at) VALUES ('zz', %s)
            ON CONFLICT (state) DO UPDATE SET min_scraped_at = EXCLUDED.min_scraped_at
            """,
            (_CUTOFF,),
        )
        await conn.commit()


async def _add_person(ocdid):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO people (id, jurisdiction_ocdid, data, updated_at, status)
            VALUES (%s, %s, %s, now(), 'current')
            """,
            (str(uuid.uuid4()), ocdid, json.dumps({"id": f"{ocdid}-p1"})),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_has_people_scraped_since_cutoff_is_fresh():
    await _insert_jurisdiction("zz-fresh", url="https://f", scraped_at=_AFTER_CUTOFF)
    await _add_person("zz-fresh")

    status = await get_local_status_for_state("zz")

    assert status["zz-fresh"] == MapStatus.FRESH


@pytest.mark.asyncio
@pytest.mark.integration
async def test_has_people_scraped_before_cutoff_is_stale():
    await _insert_jurisdiction("zz-stale", url="https://s", scraped_at=_BEFORE_CUTOFF)
    await _add_person("zz-stale")

    status = await get_local_status_for_state("zz")

    assert status["zz-stale"] == MapStatus.STALE


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_people_with_url_is_gap():
    await _insert_jurisdiction("zz-gap", url="https://g", scraped_at=_AFTER_CUTOFF)

    status = await get_local_status_for_state("zz")

    # fresh scrape but no people rows → GAP (has-data axis wins)
    assert status["zz-gap"] == MapStatus.GAP


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_people_no_url_is_untracked():
    await _insert_jurisdiction("zz-untracked", url=None, scraped_at=None)

    status = await get_local_status_for_state("zz")

    assert status["zz-untracked"] == MapStatus.UNTRACKED
