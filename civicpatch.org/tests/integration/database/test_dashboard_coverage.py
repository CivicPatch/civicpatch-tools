"""Integration test for get_dashboard's cutoff-based coverage split.

`localities` carries `covered_fresh` / `covered_stale` (+ `coverage` = their sum).
`status_counts` (fresh/stale/gap/untracked) mirrors the homepage's MapStatus taxonomy
(core/coverage.py's `classify_map_status`), and `cutoff` surfaces `state_configs.min_scraped_at`
directly. Real Postgres because it's the state_configs join + pre-aggregated people join + FILTERs.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz', cleaned before/after.
"""

import datetime
import json
import uuid

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
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid LIKE 'zz-%'")
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        await cur.execute("DELETE FROM state_configs WHERE state = 'zz'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid, *, url, scraped_at, people=False):
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
async def test_localities_split_fresh_stale_and_coverage():
    await _insert("zz-fresh", url="https://f", scraped_at=_AFTER_CUTOFF, people=True)
    await _insert("zz-stale", url="https://s", scraped_at=_BEFORE_CUTOFF, people=True)
    await _insert("zz-gap", url="https://n", scraped_at=None, people=False)

    data = await get_dashboard()

    localities = data["states"]["zz"]["civicpatch"]["localities"]
    assert localities["known"] == 3
    assert localities["scrapeable"] == 3
    assert localities["covered_fresh"] == 1  # zz-fresh
    assert localities["covered_stale"] == 1  # zz-stale
    assert localities["covered"] == 2  # covered_fresh + covered_stale (zz-gap excluded)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_status_counts_and_cutoff():
    await _insert("zz-fresh", url="https://f", scraped_at=_AFTER_CUTOFF, people=True)
    await _insert("zz-stale", url="https://s", scraped_at=_BEFORE_CUTOFF, people=True)
    await _insert("zz-gap", url="https://n", scraped_at=None, people=False)
    await _insert("zz-untracked", url=None, scraped_at=None, people=False)

    data = await get_dashboard()

    civicpatch = data["states"]["zz"]["civicpatch"]
    assert civicpatch["status_counts"] == {
        "fresh": 1,       # zz-fresh
        "stale": 1,       # zz-stale
        "gap": 1,         # zz-gap: has a url, no people
        "untracked": 1,   # zz-untracked: no url, no people
    }
    assert civicpatch["cutoff"] == _CUTOFF.isoformat()
