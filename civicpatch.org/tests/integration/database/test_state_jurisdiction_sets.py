"""Integration tests for get_state_jurisdiction_sets (coverage sets).

Real Postgres: the url/has-people/freshness partition is pure SQL.

Run with: mise run tcp-integration

Isolation: sentinel state code 'zz' + ocdid prefix; clean_sentinel_states wipes
jurisdictions and people for it each test.
"""

from tests.integration import factories
import datetime
import json
import uuid

import pytest
import pytest_asyncio

from database.database import get_pool
from database.jurisdictions import get_state_jurisdiction_sets

_SENTINEL_STATES = ("zz",)
# Freshness is a rolling 90-day window, so fixtures are ages rather than fixed dates —
# absolute dates would silently age into the wrong bucket as the calendar moves.
_NOW = datetime.datetime.now(datetime.timezone.utc)
_FRESH_SCRAPE = _NOW - datetime.timedelta(days=30)
_STALE_SCRAPE = _NOW - datetime.timedelta(days=120)


async def _wipe_sentinels():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid LIKE 'zz%'"
        )
        for _t in ("posts", "divisions", "organizations"):
            await cur.execute(
                f"DELETE FROM {_t} WHERE jurisdiction_ocdid LIKE 'zz%'"
            )
        # `collect_and_publish` mints a run and a changeset per fresh fixture, and
        # `fk_changesets_jurisdiction_ocdid` is ON DELETE RESTRICT — without these the
        # jurisdiction delete below raises and the teardown silently leaves rows behind.
        for _table in ("changesets", "pipeline_runs"):
            await cur.execute(
                f"DELETE FROM {_table} WHERE jurisdiction_ocdid LIKE 'zz%'"
            )
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid LIKE 'zz-%'")
        await cur.execute(
            "DELETE FROM jurisdictions WHERE state = ANY(%s)", (list(_SENTINEL_STATES),)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinel_states():
    await _wipe_sentinels()
    yield
    await _wipe_sentinels()


async def _insert_jurisdiction(
    ocdid, *, state="zz", url=None, collected_at=None, status="active", people=False
):
    data = json.dumps({"url": url} if url else {})
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status)
            VALUES (%s, %s, 'local', %s, now(), %s)
            """,
            (ocdid, state, data, status),
        )
        if people:
            # Seated: "has people" is an open membership now.
            await cur.execute(
                """
                WITH p AS (
                    INSERT INTO people (id, jurisdiction_ocdid, name, updated_at)
                    VALUES (gen_random_uuid(), %(ocdid)s, %(name)s, now())
                    RETURNING id
                ), o AS (
                    INSERT INTO organizations (jurisdiction_ocdid, name)
                    VALUES (%(ocdid)s, 'zz') RETURNING id
                ), d AS (
                    INSERT INTO divisions (ocdid, jurisdiction_ocdid)
                    VALUES (%(division)s, %(ocdid)s)
                    ON CONFLICT DO NOTHING RETURNING ocdid
                ), s AS (
                    INSERT INTO posts
                        (jurisdiction_ocdid, organization_id, role_id, division_ocdid)
                    SELECT %(ocdid)s, o.id, 'mayor', %(division)s FROM o
                    RETURNING id, organization_id
                )
                INSERT INTO memberships
                    (post_id, organization_id, person_id, first_seen_at, last_seen_at)
                SELECT s.id, s.organization_id, p.id, now(), now() FROM s, p
                """,
                {
                    "ocdid": ocdid,
                    "name": "x",
                    "division": ocdid.replace("ocd-jurisdiction", "ocd-division"),
                },
            )
        await conn.commit()

    # Freshness is derived from published collection changesets now, not from a column a
    # fixture can set. `collected_at=None` means never collected, which is a real state.
    if collected_at is not None:
        await factories.collect_and_publish(ocdid, collected_at)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_total_includes_all_current_excludes_inactive():
    await _insert_jurisdiction("zz-a", url="https://a", collected_at=_FRESH_SCRAPE)
    await _insert_jurisdiction("zz-b", url=None, collected_at=None)
    await _insert_jurisdiction("zz-gone", url="https://gone", status="inactive")

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.total == {"zz-a", "zz-b"}  # inactive excluded


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scrapeable_is_url_bearing_subset():
    await _insert_jurisdiction("zz-url", url="https://x")
    await _insert_jurisdiction("zz-nourl", url=None)
    await _insert_jurisdiction("zz-empty", url="")  # blank url ≠ scrapeable

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.total == {"zz-url", "zz-nourl", "zz-empty"}
    assert sets.scrapeable == {"zz-url"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_done_split_needs_url_people_and_freshness():
    # url + people + fresh → covered_fresh
    await _insert_jurisdiction(
        "zz-fresh", url="https://f", collected_at=_FRESH_SCRAPE, people=True
    )
    # url + people + old → covered_stale
    await _insert_jurisdiction(
        "zz-stale", url="https://s", collected_at=_STALE_SCRAPE, people=True
    )
    # url + people + never stamped → covered_stale (NULL is not fresh)
    await _insert_jurisdiction(
        "zz-null", url="https://n", collected_at=None, people=True
    )
    # url, fresh, but NO people → neither (it's a gap)
    await _insert_jurisdiction(
        "zz-nopeople", url="https://g", collected_at=_FRESH_SCRAPE, people=False
    )
    # people + fresh but NO url → not scrapeable → neither
    await _insert_jurisdiction(
        "zz-nourl", url=None, collected_at=_FRESH_SCRAPE, people=True
    )

    sets = await get_state_jurisdiction_sets("zz")

    assert sets.covered_fresh == {"zz-fresh"}
    assert sets.covered_stale == {"zz-stale", "zz-null"}
    assert sets.scrapeable == {"zz-fresh", "zz-stale", "zz-null", "zz-nopeople"}
