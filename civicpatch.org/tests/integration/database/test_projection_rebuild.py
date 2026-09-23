"""`rebuild`: the projection replaced from a derived roster, and R6 (rebuild twice, same rows).

Nothing publishes here. Facts go in through the factories, the fold derives a roster, and the
writer lays it down; then the stored side must equal the derived side, and laying it down
again must change nothing.

Isolation: sentinel state 'zr', cleaned before and after.
"""

import datetime
import uuid

import pytest
import pytest_asyncio
from shared.schemas import RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.projection.diff import on_roster, roster_diff
from core.projection.live_facts import live_facts
from core.projection.posts import post_keys
from core.projection.roster import derive_roster
from database.database import get_pool
from database.facts import load_facts
from database.projection import rebuild, stored_roster
from database.roles import get_roles
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zr/place:rebuildton/government"
_PAGE = "https://zr.gov/council"
_T0 = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)
_T1 = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zr'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> dict:
    ids = {"ana": str(uuid.uuid4()), "ben": str(uuid.uuid4())}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zr', 'local')",
            (_OCDID,),
        )
        ids["council"] = await factories.default_organization(cur, _OCDID)
        await conn.commit()
    return ids


async def _scrape(ids: dict, at, listing: dict[str, str]) -> None:
    """One published read of the council listing each person with a label."""
    await factories.published_scrape(
        _OCDID,
        at,
        {
            ids[person]: [
                {
                    "name": person.title(),
                    "label": label,
                    "source_url": _PAGE,
                    "url": _PAGE,
                    "organization_id": ids["council"],
                }
            ]
            for person, label in listing.items()
        },
    )


async def _rebuild() -> None:
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        facts = await load_facts(cur, _OCDID, datetime.datetime.now(datetime.timezone.utc))
        roster = derive_roster(facts, _OCDID, taxonomy, roles)
        keys = post_keys(live_facts(facts).records, _OCDID, taxonomy, roles)
        await rebuild(cur, _OCDID, roster, keys)
        await conn.commit()


async def _stored_and_derived():
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        stored = await stored_roster(cur, _OCDID)
        facts = await load_facts(cur, _OCDID, datetime.datetime.now(datetime.timezone.utc))
    return on_roster(stored), on_roster(derive_roster(facts, _OCDID, taxonomy, roles))


async def _membership_rows() -> list[tuple]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT m.id::text, m.person_id::text, m.post_id::text, m.first_seen_at, m.closed_at "
            "FROM memberships m JOIN posts p ON p.id = m.post_id "
            "WHERE p.jurisdiction_ocdid = %s ORDER BY m.id",
            (_OCDID,),
        )
        return await cur.fetchall()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_stored_projection_equals_the_derived_roster():
    ids = await _seed()
    await _scrape(ids, _T0, {"ana": "Mayor", "ben": "Council Member"})

    await _rebuild()

    stored, derived = await _stored_and_derived()
    assert roster_diff(stored, derived).empty
    assert {person.id for person in stored.people} == {ids["ana"], ids["ben"]}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rebuilding_twice_changes_no_row():
    """R6."""
    ids = await _seed()
    await _scrape(ids, _T0, {"ana": "Mayor", "ben": "Council Member"})
    await _rebuild()
    first = await _membership_rows()

    await _rebuild()

    assert await _membership_rows() == first
    assert first[0][3] == _T0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_person_the_latest_read_dropped_loses_the_row_not_a_closed_at():
    ids = await _seed()
    await _scrape(ids, _T0, {"ana": "Mayor", "ben": "Council Member"})
    await _rebuild()
    await _scrape(ids, _T1, {"ben": "Council Member"})

    await _rebuild()

    rows = await _membership_rows()
    assert [row[1] for row in rows] == [ids["ben"]]
    assert rows[0][3] == _T0
    assert rows[0][4] is None
    stored, derived = await _stored_and_derived()
    assert roster_diff(stored, derived).empty
