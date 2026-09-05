"""Integration tests for get_local_status_for_state (map colors).

Real Postgres: the freshness/has-people/has-url flags are SQL; the FRESH/STALE/GAP/
UNTRACKED call is the pure core.coverage.classify_map_status. This locks the two
together against real rows.

Run with: mise run tcp-integration

Isolation: sentinel state 'zz' + ocdid prefix 'zz-'; cleaned before/after each test.
"""

from tests.integration import factories
import datetime
import json
import uuid

import pytest
import pytest_asyncio

from core.coverage import MapStatus
from database.coverage import get_local_status_for_state
from database.database import get_pool

# Freshness is a rolling 3-month window, so fixtures are ages rather than fixed dates —
# absolute dates would silently age into the wrong bucket as the calendar moves.
_NOW = datetime.datetime.now(datetime.timezone.utc)
_FRESH_SCRAPE = _NOW - datetime.timedelta(days=30)
_STALE_SCRAPE = _NOW - datetime.timedelta(days=120)


async def _wipe():
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
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert_jurisdiction(ocdid, *, url=None, collected_at=None):
    data = json.dumps({"url": url} if url else {})
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status)
            VALUES (%s, 'zz', 'local', %s, now(), 'active')
            """,
            (ocdid, data),
        )
        await conn.commit()

    # Freshness is derived from published collection changesets now, not from a column a
    # fixture can set. `collected_at=None` means never collected, which is a real state.
    if collected_at is not None:
        await factories.collect_and_publish(ocdid, collected_at)
async def _add_person(ocdid):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
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
                "name": f"{ocdid}-p1",
                "division": ocdid.replace("ocd-jurisdiction", "ocd-division"),
            },
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_has_people_scraped_within_window_is_fresh():
    await _insert_jurisdiction("zz-fresh", url="https://f", collected_at=_FRESH_SCRAPE)
    await _add_person("zz-fresh")

    status = await get_local_status_for_state("zz")

    assert status["zz-fresh"] == MapStatus.FRESH


@pytest.mark.asyncio
@pytest.mark.integration
async def test_has_people_scraped_before_window_is_stale():
    await _insert_jurisdiction("zz-stale", url="https://s", collected_at=_STALE_SCRAPE)
    await _add_person("zz-stale")

    status = await get_local_status_for_state("zz")

    assert status["zz-stale"] == MapStatus.STALE


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_people_with_url_is_gap():
    await _insert_jurisdiction("zz-gap", url="https://g", collected_at=_FRESH_SCRAPE)

    status = await get_local_status_for_state("zz")

    # fresh scrape but no people rows → GAP (has-data axis wins)
    assert status["zz-gap"] == MapStatus.GAP


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_people_no_url_is_untracked():
    await _insert_jurisdiction("zz-untracked", url=None, collected_at=None)

    status = await get_local_status_for_state("zz")

    assert status["zz-untracked"] == MapStatus.UNTRACKED
