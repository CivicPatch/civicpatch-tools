"""Merges, splits and the matcher, through the real loader and rollback (plan step 6).

Integration twins of `.scratch/2026-09-19-rollback-simulator.html` scenarios 6, 12, 24, 25 and
26. The simulator holds several posts per organization; the fold keeps one membership per
organization, so these assert on organizations held rather than posts.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from core.projection.people import Person
from database import claims as claims_db
from database import projection as projection_db
from database.changesets import register_roster_edit_changeset
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.claims import Claim, ClaimKind, DefaultNote, EntityType, Source
from schemas.jurisdictions import OfficeEdit, PersonEdit
from services import rollback
from services.roster_edits import edit_published_roster
from services.roster_ingest import assign_ids
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_identity/government"
_PAGE = "https://zz-identity.gov/council"
_T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(days=7)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM claims WHERE changeset_id IN "
            "(SELECT id FROM changesets WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "changesets", "organizations", "people"):
            await cur.execute(f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _organizations() -> tuple[str, str]:
    """(council, school)."""
    await factories.seed_jurisdiction(_OCDID, "zz", name="Identity Ville")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        council = await factories.default_organization(cur, _OCDID)
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, 'School Board') "
            "RETURNING id::text",
            (_OCDID,),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    return council, row[0]


def _record(name: str, label: str, organization_id: str, phone: str | None = None) -> dict:
    return {
        "name": name,
        "label": label,
        "source_url": _PAGE,
        "organization_id": organization_id,
        "phone": phone,
    }


async def _scrape(at: datetime, records: dict[str, list[dict]]) -> None:
    """Published at `at`. Rebuilt directly: `publish_changeset` would refuse a scrape dated
    before an edit, and these scrapes are backdated so their records have a known timestamp."""
    await factories.published_scrape(_OCDID, at, records)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await projection_db.rebuild_from_facts(cur, _OCDID)
        await conn.commit()


async def _merge(absorbed_id: str, survivor_id: str) -> str:
    return await edit_published_roster(
        _OCDID, [PersonEdit(id=absorbed_id, same_as=survivor_id)], SYSTEM_USER_ID
    )


async def _split(record_id: str, person_id: str) -> str:
    """Re-link one record to another person. No route files this yet; the fold and the
    loader are what is under test."""
    changeset_id = str(uuid.uuid4())
    await register_roster_edit_changeset(changeset_id, _OCDID, SYSTEM_USER_ID)
    await claims_db.create_all(
        [
            Claim(
                entity_type=EntityType.SOURCE_RECORD,
                entity_id=record_id,
                field_path="person_id",
                kind=ClaimKind.ACCEPT,
                value=person_id,
                sources=[Source(note=DefaultNote.EDITED)],
                changeset_id=changeset_id,
            )
        ],
        SYSTEM_USER_ID,
    )
    return changeset_id


async def _undo(changeset_id: str) -> None:
    await rollback.rollback_changeset(changeset_id, SYSTEM_USER_ID, "not the same person")


async def _roster() -> dict[str, Person]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        roster = await projection_db.derived_roster(cur, _OCDID)
    return {person.id: person for person in roster.people}


def _has_phone(person: Person, digits: str) -> bool:
    return any(digits in "".join(ch for ch in phone if ch.isdigit()) for phone in person.phones)


def _organizations_of(person: Person) -> set[str]:
    return {membership.post.organization_id for membership in person.memberships}


async def _record_id(label: str, at: datetime) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM source_records "
            "WHERE jurisdiction_ocdid = %s AND label = %s AND created_at = %s",
            (_OCDID, label, at),
        )
        row = await cur.fetchone()
        assert row is not None
        return row[0]


def _ids() -> tuple[str, ...]:
    return tuple(str(uuid.uuid4()) for _ in range(3))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_6_a_record_scraped_during_a_merge_stays_with_its_base_identity():
    council, school = await _organizations()
    a1, a2, _ = _ids()
    await _scrape(_T0, {
        a1: [_record("A. Smith", "Mayor", council)],
        a2: [_record("Alice Smith", "Council Member", school, "(415) 555-0199")],
    })
    merge = await _merge(a1, a2)

    roster = await _roster()
    assert set(roster) == {a2}
    assert _organizations_of(roster[a2]) == {council, school}

    # The matcher links a new sighting to the base identity, never the merged cluster.
    [linked] = await assign_ids(_OCDID, [{"name": "A. Smith"}])
    assert linked["id"] == a1
    await _scrape(_T1, {a1: [_record("A. Smith", "Mayor", council, "(415) 555-0101")]})
    assert _has_phone((await _roster())[a2], "4155550101")

    await _undo(merge)

    roster = await _roster()
    assert set(roster) == {a1, a2}
    assert _organizations_of(roster[a1]) == {council}
    assert _has_phone(roster[a1], "4155550101")
    assert _organizations_of(roster[a2]) == {school}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_12_a_split_re_links_one_record_and_rolls_back():
    council, _ = await _organizations()
    alice, alice_jr, _ = _ids()
    await _scrape(_T0, {alice: [
        _record("Alice Ng", "Mayor", council),
        _record("Alice Ng Jr", "Council Member", council),
    ]})
    second = await _record_id("Council Member", _T0)

    split = await _split(second, alice_jr)

    roster = await _roster()
    assert set(roster) == {alice, alice_jr}
    assert roster[alice_jr].name == "Alice Ng Jr"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT person_id::text FROM source_records WHERE id = %s", (second,))
        assert await cur.fetchone() == (alice,), "the record itself is never rewritten"

    await _undo(split)

    assert set(await _roster()) == {alice}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_24_unmerging_the_middle_of_a_chain_splits_it_there():
    council, _ = await _organizations()
    a, b, c = _ids()
    await _scrape(_T0, {
        a: [_record("Ann Adams", "Mayor", council)],
        b: [_record("Ben Brown", "Council Member", council)],
        c: [_record("Cy Chen", "Council Member", council)],
    })
    first = await _merge(a, b)
    second = await _merge(b, c)
    assert set(await _roster()) == {c}

    await _undo(second)
    assert set(await _roster()) == {b, c}

    await _undo(first)
    assert set(await _roster()) == {a, b, c}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_25_an_edit_made_during_a_merge_stays_on_the_survivor():
    council, school = await _organizations()
    a1, a2, _ = _ids()
    await _scrape(_T0, {
        a1: [_record("A. Smith", "Mayor", council)],
        a2: [_record("Alice Smith", "Council Member", school)],
    })
    merge = await _merge(a1, a2)
    await edit_published_roster(
        _OCDID, [PersonEdit(id=a2, fields={"phones": ["(415) 555-0177"]})], SYSTEM_USER_ID
    )

    await _undo(merge)

    roster = await _roster()
    assert len(roster[a2].phones) == 1
    assert roster[a1].phones == ()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_26_the_matcher_finds_a_hand_added_person_and_a_split_sticks():
    council, _ = await _organizations()
    seated, _, _ = _ids()
    await _scrape(_T0, {seated: [_record("Dee Dunn", "Mayor", council)]})
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM posts WHERE jurisdiction_ocdid = %s LIMIT 1", (_OCDID,)
        )
        row = await cur.fetchone()
        assert row is not None
    bob = str(uuid.uuid4())
    await edit_published_roster(
        _OCDID,
        [PersonEdit(
            id=bob,
            fields={"name": "Bob Ito", "jurisdiction_ocdid": _OCDID, "source_urls": [_PAGE]},
            offices=[OfficeEdit(id=row[0])],
        )],
        SYSTEM_USER_ID,
    )

    assert bob in await _roster(), "a hand-add is claims only, and derives"
    [found] = await assign_ids(_OCDID, [{"name": "Bob Ito"}])
    assert found["id"] == bob, "claims only, and still in the matcher's pool"

    await _scrape(_T1, {bob: [
        _record("Bob Ito", "Council Member", council),
        _record("Bob Ito", "Clerk", council),
    ]})
    bob_sr = str(uuid.uuid4())
    await _split(await _record_id("Clerk", _T1), bob_sr)
    await edit_published_roster(
        _OCDID, [PersonEdit(id=bob_sr, fields={"name": "Bob Ito Sr"})], SYSTEM_USER_ID
    )

    resolved = await assign_ids(_OCDID, [{"name": "Bob Ito"}, {"name": "Bob Ito Sr"}])
    assert [person["id"] for person in resolved] == [bob, bob_sr], "no duplicate minted"
