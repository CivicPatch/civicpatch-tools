"""Integration test for get_dashboard's cutoff-based `coverage` count.

After the swap, `coverage` = jurisdictions scraped since the state's cutoff (not
"has any people"). Real Postgres because it's the state_configs join + FILTER.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz', cleaned before/after.
"""

import datetime
import json

import pytest
import pytest_asyncio

from database.dashboard import get_dashboard
from database.database import get_pool

_CUTOFF = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
_AFTER_CUTOFF = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
_BEFORE_CUTOFF = datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        await cur.execute("DELETE FROM state_configs WHERE state = 'zz'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid, *, url, scraped_at):
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_coverage_counts_scraped_since_cutoff():
    await _insert("zz-fresh", url="https://f", scraped_at=_AFTER_CUTOFF)
    await _insert("zz-stale", url="https://s", scraped_at=_BEFORE_CUTOFF)
    await _insert("zz-never", url="https://n", scraped_at=None)

    data = await get_dashboard()

    localities = data["states"]["zz"]["civicpatch"]["localities"]
    assert localities["known"] == 3
    assert localities["scrapeable"] == 3
    assert localities["coverage"] == 1  # only zz-fresh is scraped since cutoff
