"""Integration test for get_dashboard's freshness-based coverage split.

`localities` carries `covered_fresh` / `covered_stale` (+ `coverage` = their sum).
`status_counts` (fresh/stale/gap/untracked) mirrors the homepage's MapStatus taxonomy
(core/coverage.py's `classify_map_status`), and `cutoff` surfaces the start of the rolling
freshness window. Real Postgres because it's the pre-aggregated people join + FILTERs.

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


async def _insert(ocdid, *, url, scraped_at, people=False):
    data = json.dumps({"url": url} if url else {})
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
                INSERT INTO people (id, jurisdiction_ocdid, data, updated_at, status)
                VALUES (%s, %s, %s, now(), 'active')
                """,
                (str(uuid.uuid4()), ocdid, json.dumps({"name": "x"})),
            )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_localities_split_fresh_stale_and_coverage():
    await _insert("zz-fresh", url="https://f", scraped_at=_FRESH_SCRAPE, people=True)
    await _insert("zz-stale", url="https://s", scraped_at=_STALE_SCRAPE, people=True)
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
async def test_never_scraped_with_people_counts_as_stale():
    # NULL scraped_at = officials arrived via sync, never scraped by us.
    await _insert("zz-fresh", url="https://f", scraped_at=_FRESH_SCRAPE, people=True)
    await _insert("zz-null", url="https://n", scraped_at=None, people=True)

    civicpatch = (await get_dashboard())["states"]["zz"]["civicpatch"]

    assert civicpatch["localities"]["covered_stale"] == 1  # zz-null
    assert civicpatch["status_counts"]["stale"] == 1
    # every known jurisdiction lands in exactly one status bucket
    assert sum(civicpatch["status_counts"].values()) == civicpatch["localities"]["known"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_status_counts_and_cutoff():
    await _insert("zz-fresh", url="https://f", scraped_at=_FRESH_SCRAPE, people=True)
    await _insert("zz-stale", url="https://s", scraped_at=_STALE_SCRAPE, people=True)
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
    # The reported cutoff is what the frontend renders as "Fresh = scraped after X", so it
    # has to be the same boundary that produced the split above — assert that relationship
    # rather than an exact timestamp, which is server-computed at query time.
    cutoff = datetime.datetime.fromisoformat(civicpatch["cutoff"])
    assert _STALE_SCRAPE < cutoff < _FRESH_SCRAPE
