"""`rebuild`: the projection replaced from a derived roster, and R6 (rebuild twice, same rows).

Nothing publishes here except the preview test at the end. Facts go in through the factories,
the fold derives a roster, and the writer lays it down; then the stored side must equal the
derived side, and laying it down again must change nothing.

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
from database.projection import derived_roster, rebuild, stored_roster
from database.publications import publish_changeset
from database.roles import get_roles
from database.source_records import insert_source_records
from services.roster import card_sides, published_card_rows
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
        roster = derive_roster(facts, _OCDID, taxonomy)
        keys = post_keys(live_facts(facts).records, _OCDID, taxonomy)
        await rebuild(cur, _OCDID, roster, keys)
        await conn.commit()


async def _stored_and_derived():
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        stored = await stored_roster(cur, _OCDID)
        facts = await load_facts(cur, _OCDID, datetime.datetime.now(datetime.timezone.utc))
    return on_roster(stored), on_roster(derive_roster(facts, _OCDID, taxonomy))


async def _membership_rows() -> list[tuple]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT m.id::text, m.person_id::text, m.post_id::text, m.opened_at, m.closed_at "
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


async def _unpublished_scrape(ids: dict, listing: dict[str, str]) -> str:
    """A scrape awaiting review: its records are stored, and no roster derives them yet."""
    changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind) VALUES (%s, %s, 'scrape')",
            (changeset_id, _OCDID),
        )
        await conn.commit()
    await insert_source_records(
        changeset_id,
        _OCDID,
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
    return changeset_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_preview_of_a_changeset_is_what_publishing_it_produces():
    """What makes a review card trustworthy: the reviewer is shown `derive(published + X)`,
    and publishing X runs the same fold over the same facts. If these two could differ, every
    card would be a guess."""
    ids = await _seed()
    await _scrape(ids, _T0, {"ana": "Mayor"})
    proposed = await _unpublished_scrape(ids, {"ana": "Mayor", "ben": "Council Member"})

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        preview = await derived_roster(cur, _OCDID, including=proposed)

    await publish_changeset(proposed, _OCDID)
    async with pool.connection() as conn, conn.cursor() as cur:
        published = await derived_roster(cur, _OCDID)

    assert roster_diff(on_roster(preview), on_roster(published)).empty


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_card_s_two_sides_are_the_same_fold():
    """The rows the review card renders, one layer above the preview: `existing` is what the
    facts derive today and `proposed` what they derive with this changeset counted in. Here
    rather than beside the service, because the seeding this claim needs is all in this file."""
    ids = await _seed()
    await _scrape(ids, _T0, {"ana": "Mayor"})
    await _rebuild()
    proposed = await _unpublished_scrape(ids, {"ana": "Mayor", "ben": "Council Member"})

    existing = await published_card_rows(_OCDID)
    preview = (await card_sides(proposed, _OCDID)).proposed

    assert [row["id"] for row in existing] == [ids["ana"]]
    assert sorted(row["id"] for row in preview) == sorted([ids["ana"], ids["ben"]])
    # `PERSON_JSON`'s shape, which is what makes this a swap and not a payload change.
    assert [membership["post_label"] for membership in preview[0]["memberships"]]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_preview_writes_nothing():
    """Read-only: a card may be drawn a hundred times and the roster is whatever the published
    facts say until somebody approves it."""
    ids = await _seed()
    await _scrape(ids, _T0, {"ana": "Mayor"})
    await _rebuild()
    proposed = await _unpublished_scrape(ids, {"ben": "Council Member"})

    before = await _membership_rows()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        preview = await derived_roster(cur, _OCDID, including=proposed)

    # `on_roster`: Ana's records still exist, so she is still a person — the page the review
    # proposes just does not put her in anything.
    assert [person.id for person in on_roster(preview).people] == [ids["ben"]]
    assert await _membership_rows() == before
