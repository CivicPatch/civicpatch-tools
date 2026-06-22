"""Integration tests for get_state_jurisdiction_sets (coverage denominators).

Real Postgres: the function is pure SQL at the DB boundary (the cutoff join +
url/freshness partition), so mocking a cursor would only re-assert the SQL string.

Run with: mise run tcp-integration

Isolation: sentinel state codes ('zz' has a config row, 'zy' has none) that can't
collide with real states; clean_sentinel_states wipes them before/after each test.
"""

import datetime
import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.jurisdictions import get_state_jurisdiction_sets

_SENTINEL_STATES = ("zz", "zy")
_CUTOFF = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
_AFTER_CUTOFF = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
_BEFORE_CUTOFF = datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc)


async def _wipe_sentinels():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM jurisdictions WHERE state = ANY(%s)", (list(_SENTINEL_STATES),)
        )
        await cur.execute(
            "DELETE FROM state_configs WHERE state = ANY(%s)", (list(_SENTINEL_STATES),)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinel_states():
    await _wipe_sentinels()
    yield
    await _wipe_sentinels()


async def _insert_jurisdiction(
    ocdid, *, state="zz", url=None, scraped_at=None, status="current"
):
    data = json.dumps({"url": url} if url else {})
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status, scraped_at)
            VALUES (%s, %s, 'local', %s, now(), %s, %s)
            """,
            (ocdid, state, data, status, scraped_at),
        )
        await conn.commit()


async def _set_cutoff(state, cutoff):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO state_configs (state, min_scraped_at) VALUES (%s, %s)
            ON CONFLICT (state) DO UPDATE SET min_scraped_at = EXCLUDED.min_scraped_at
            """,
            (state, cutoff),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_total_includes_all_current_excludes_inactive():
    await _set_cutoff("zz", _CUTOFF)
    await _insert_jurisdiction("zz-a", url="https://a", scraped_at=_AFTER_CUTOFF)
    await _insert_jurisdiction("zz-b", url=None, scraped_at=None)
    await _insert_jurisdiction("zz-gone", url="https://gone", status="inactive")

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.total == {"zz-a", "zz-b"}  # inactive excluded


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scrapeable_is_url_bearing_subset():
    await _set_cutoff("zz", _CUTOFF)
    await _insert_jurisdiction("zz-url", url="https://x", scraped_at=None)
    await _insert_jurisdiction("zz-nourl", url=None, scraped_at=None)
    await _insert_jurisdiction("zz-empty", url="", scraped_at=None)  # blank url ≠ scrapeable

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.total == {"zz-url", "zz-nourl", "zz-empty"}
    assert sets.scrapeable == {"zz-url"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_done_is_scraped_since_cutoff_only():
    await _set_cutoff("zz", _CUTOFF)
    await _insert_jurisdiction("zz-fresh", url="https://f", scraped_at=_AFTER_CUTOFF)
    await _insert_jurisdiction("zz-stale", url="https://s", scraped_at=_BEFORE_CUTOFF)
    await _insert_jurisdiction("zz-never", url="https://n", scraped_at=None)

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.scrapeable == {"zz-fresh", "zz-stale", "zz-never"}
    assert sets.done == {"zz-fresh"}  # before-cutoff and never-scraped are not done


@pytest.mark.asyncio
@pytest.mark.integration
async def test_done_excludes_fresh_scrape_without_url():
    # scraped_at set but no url → not scrapeable, so not counted as done
    await _set_cutoff("zz", _CUTOFF)
    await _insert_jurisdiction("zz-nourl-fresh", url=None, scraped_at=_AFTER_CUTOFF)

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.scrapeable == set()
    assert sets.done == set()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_state_config_treats_cutoff_as_epoch():
    # state 'zy' has no state_configs row → cutoff falls back to epoch, so ANY non-null
    # scraped_at counts as done; only never-scraped stays out.
    await _insert_jurisdiction(
        "zy-old", state="zy", url="https://o", scraped_at=_BEFORE_CUTOFF
    )
    await _insert_jurisdiction("zy-never", state="zy", url="https://n", scraped_at=None)

    sets = await get_state_jurisdiction_sets("zy")

    assert sets.done == {"zy-old"}  # epoch cutoff → old scrape still counts
