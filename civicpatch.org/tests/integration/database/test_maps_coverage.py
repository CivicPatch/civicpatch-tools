"""Integration test for get_maps_coverage's fresh/scraped/total counts.

Real Postgres: the people pre-agg join + rolling freshness window + parent_ocdids county
expansion. Verifies `fresh` (has-data + recently scraped) sits alongside `scraped` (has-data)
at both state and county level, so the map can shade by staleness.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz' + ocdid prefix, cleaned before/after.
"""

from tests.integration import factories
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
        # The posts chain first: `memberships.person_id` is a FK, and these fixtures seat
        # their people now.
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid LIKE 'zz-%'"
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid LIKE 'zz-%'"
            )
        # `collect_and_publish` mints a run and a changeset per fresh fixture, and
        # `fk_changesets_jurisdiction_ocdid` is ON DELETE RESTRICT — without these the
        # jurisdiction delete below raises and the teardown silently leaves rows behind.
        for _table in ("changesets", "pipeline_runs"):
            await cur.execute(
                f"DELETE FROM {_table} WHERE jurisdiction_ocdid LIKE 'zz%'"
            )
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid, *, collected_at, people):
    data = json.dumps({"url": "https://x", "parent_ocdids": [_COUNTY]})
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
        if people:
            # Seated, not merely present: "has people" is an open membership now, so a person
            # with no seat does not count — which is what the column used to hide.
            await cur.execute(
                """
                WITH p AS (
                    INSERT INTO people (id, jurisdiction_ocdid, name, updated_at)
                    VALUES (gen_random_uuid(), %(ocdid)s, 'x', now())
                    RETURNING id
                ), o AS (
                    INSERT INTO organizations (jurisdiction_ocdid, name)
                    VALUES (%(ocdid)s, 'zz') RETURNING id
                ), d AS (
                    INSERT INTO divisions (ocdid, jurisdiction_ocdid)
                    VALUES (%(division)s, %(ocdid)s) RETURNING ocdid
                ), s AS (
                    INSERT INTO posts
                        (jurisdiction_ocdid, organization_id, role_id, division_ocdid)
                    SELECT %(ocdid)s, o.id, 'mayor', d.ocdid FROM o, d
                    RETURNING id, organization_id
                )
                INSERT INTO memberships
                    (post_id, organization_id, person_id, first_seen_at, last_seen_at)
                SELECT s.id, s.organization_id, p.id, now(), now() FROM s, p
                """,
                {"ocdid": ocdid, "division": ocdid.replace("ocd-jurisdiction", "ocd-division")},
            )
        await conn.commit()

    # Freshness is derived from published collection changesets now, not from a column a
    # fixture can set. `collected_at=None` means never collected, which is a real state.
    if collected_at is not None:
        await factories.collect_and_publish(ocdid, collected_at)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fresh_sits_alongside_scraped_and_total():
    await _insert("zz-fresh", collected_at=_FRESH_SCRAPE, people=True)
    await _insert("zz-stale", collected_at=_STALE_SCRAPE, people=True)
    await _insert("zz-nopeople", collected_at=_FRESH_SCRAPE, people=False)

    coverage = await get_maps_coverage()

    state = coverage["zz"]["state"]
    assert state["total"] == 3
    assert state["covered"] == 2  # zz-fresh + zz-stale have people
    assert state["covered_fresh"] == 1  # only zz-fresh is since cutoff

    county = coverage["zz"]["counties"][_COUNTY]
    assert county["total"] == 3
    assert county["covered"] == 2
    assert county["covered_fresh"] == 1
