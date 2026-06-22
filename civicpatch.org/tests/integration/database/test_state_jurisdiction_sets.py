"""Integration tests for get_state_jurisdiction_sets (coverage sets).

Real Postgres: the cutoff join + url/has-people/freshness partition is pure SQL.

Run with: mise run tcp-integration

Isolation: sentinel state codes ('zz' has a config row, 'zy' has none) + ocdid prefixes;
clean_sentinel_states wipes jurisdictions, people, and configs for them each test.
"""

import datetime
import json
import uuid

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
            "DELETE FROM people WHERE jurisdiction_ocdid LIKE 'zz-%' "
            "OR jurisdiction_ocdid LIKE 'zy-%'"
        )
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
    ocdid, *, state="zz", url=None, scraped_at=None, status="current", people=False
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
        if people:
            await cur.execute(
                """
                INSERT INTO people (id, jurisdiction_ocdid, data, updated_at, status)
                VALUES (%s, %s, %s, now(), 'current')
                """,
                (str(uuid.uuid4()), ocdid, json.dumps({"name": "x"})),
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
    await _insert_jurisdiction("zz-url", url="https://x")
    await _insert_jurisdiction("zz-nourl", url=None)
    await _insert_jurisdiction("zz-empty", url="")  # blank url ≠ scrapeable

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.total == {"zz-url", "zz-nourl", "zz-empty"}
    assert sets.scrapeable == {"zz-url"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_done_split_needs_url_people_and_freshness():
    await _set_cutoff("zz", _CUTOFF)
    # url + people + fresh → covered_fresh
    await _insert_jurisdiction(
        "zz-fresh", url="https://f", scraped_at=_AFTER_CUTOFF, people=True
    )
    # url + people + old → covered_stale
    await _insert_jurisdiction(
        "zz-stale", url="https://s", scraped_at=_BEFORE_CUTOFF, people=True
    )
    # url + people + never stamped → covered_stale (NULL is not fresh)
    await _insert_jurisdiction(
        "zz-null", url="https://n", scraped_at=None, people=True
    )
    # url, fresh, but NO people → neither (it's a gap)
    await _insert_jurisdiction(
        "zz-nopeople", url="https://g", scraped_at=_AFTER_CUTOFF, people=False
    )
    # people + fresh but NO url → not scrapeable → neither
    await _insert_jurisdiction(
        "zz-nourl", url=None, scraped_at=_AFTER_CUTOFF, people=True
    )

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.covered_fresh == {"zz-fresh"}
    assert sets.covered_stale == {"zz-stale", "zz-null"}
    assert sets.scrapeable == {"zz-fresh", "zz-stale", "zz-null", "zz-nopeople"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_state_config_treats_cutoff_as_epoch():
    # 'zy' has no config row → cutoff falls back to epoch, so any stamped scrape with
    # people is fresh; only never-scraped / people-less stay out of covered_fresh.
    await _insert_jurisdiction(
        "zy-old", state="zy", url="https://o", scraped_at=_BEFORE_CUTOFF, people=True
    )

    sets = await get_state_jurisdiction_sets("zy")

    assert sets.covered_fresh == {"zy-old"}  # epoch cutoff → old scrape still fresh
    assert sets.covered_stale == set()
