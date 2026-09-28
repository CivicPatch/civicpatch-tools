"""Rollback through the real loader, edit route and rollback service (projector plan step 8).

Integration twins of `.scratch/2026-09-19-rollback-simulator.html` scenarios 1, 2, 9, 14, 15, 17
and 18. Where the model differs from the simulator: phones are a set here, so the one-value
scenarios edit `name` and `image`; a person holds one membership per organization, so 9 adds a
post in a second one; 14 files one rollback changeset per changeset rolled back, and its third act of vandalism is
an image rather than a removal, since the edit route cannot edit or merge anyone off the roster. 16 has no
twin: there is no way to withdraw your own override, only to replace it or roll the edit back.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from core.projection.people import Person
from database import projection as projection_db
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.common import UserRole
from schemas.jurisdictions import OfficeEdit, PersonEdit
from services import rollback
from services.roster_edits import edit_published_roster
from shared.utils.statuses import ChangesetKind
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_rollback_scenarios/government"
_PAGE = "https://zz-rollback-scenarios.gov/council"
_PAGE_IMAGE = "https://zz-rollback-scenarios.gov/alice.jpg"
_T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
_EMAILS = {
    name: f"zz-rollback-scenarios-{name}@example.com" for name in ("carol", "dave", "troll")
}


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
        await cur.execute("DELETE FROM source_records WHERE jurisdiction_ocdid = %s", (_OCDID,))
        for table in ("posts", "divisions", "changesets", "organizations", "people"):
            await cur.execute(f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM users WHERE email = ANY(%s)", (list(_EMAILS.values()),))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _user(name: str) -> str:
    email = _EMAILS[name]
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'github', %s, %s, %s) RETURNING id::text",
            (email, email, email.replace("@", "-"), UserRole.MAINTAINERS.value),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    return row[0]


async def _organizations() -> tuple[str, str]:
    """(council, school)."""
    await factories.seed_jurisdiction(_OCDID, "zz", name="Rollback Scenarios")
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


def _record(name: str, label: str, organization_id: str) -> dict:
    return {
        "name": name,
        "label": label,
        "source_url": _PAGE,
        "organization_id": organization_id,
        "image": _PAGE_IMAGE,
    }


async def _scrape(at: datetime, records: dict[str, list[dict]]) -> str:
    """Published at `at` and rebuilt directly, as `test_identity_scenarios` does."""
    changeset_id = await factories.published_scrape(_OCDID, at, records)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await projection_db.rebuild_from_facts(cur, _OCDID)
        await conn.commit()
    return changeset_id


async def _edit(user_id: str, person: PersonEdit) -> str:
    return await edit_published_roster(_OCDID, [person], user_id)


async def _roll_back(changeset_id: str) -> str:
    """The id of the rollback changeset, since undoing an undo is rolling that back."""
    await rollback.rollback_changeset(changeset_id, SYSTEM_USER_ID, "rolled back in a test")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s AND kind = 'rollback' "
            "ORDER BY created_at DESC LIMIT 1",
            (_OCDID,),
        )
        row = await cur.fetchone()
        assert row is not None
        return row[0]


async def _roster() -> dict[str, Person]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        roster = await projection_db.derived_roster(cur, _OCDID)
    return {person.id: person for person in roster.people}


async def _on_roster() -> dict[str, Person]:
    return {id: person for id, person in (await _roster()).items() if person.memberships}


def _organizations_of(person: Person) -> set[str]:
    return {membership.post.organization_id for membership in person.memberships}


async def _post_of(organization_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM posts WHERE organization_id::text = %s", (organization_id,)
        )
        [row] = await cur.fetchall()
    return row[0]


async def _membership_rows(person_id: str) -> list[tuple[datetime, datetime | None]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT opened_at, closed_at FROM memberships WHERE person_id::text = %s "
            "ORDER BY opened_at",
            (person_id,),
        )
        return list(await cur.fetchall())


def _ids() -> tuple[str, ...]:
    return tuple(str(uuid.uuid4()) for _ in range(2))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_1_a_scrape_rolled_back_then_the_rollback_undone():
    council, _ = await _organizations()
    alice, bob = _ids()
    scrape = await _scrape(_T0, {
        alice: [_record("Alice Ng", "Mayor", council)],
        bob: [_record("Bob Ito", "Council Member", council)],
    })
    assert set(await _on_roster()) == {alice, bob}

    undo = await _roll_back(scrape)

    assert await _roster() == {}
    assert await _membership_rows(alice) == [], "a rolled-back scrape leaves no ended term"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM source_records WHERE changeset_id::text = %s", (scrape,)
        )
        assert await cur.fetchone() == (2,), "the scrape's records are kept, withdrawn"

    await _roll_back(undo)

    assert set(await _on_roster()) == {alice, bob}
    for person_id in (alice, bob):
        assert await _membership_rows(person_id) == [(_T0, None)], (
            "the term starts at the original scrape, not at the undo"
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_2_a_vandal_rolled_back_while_a_later_scrape_agrees_with_the_page():
    council, _ = await _organizations()
    alice, _ = _ids()
    vandal = await _user("troll")
    await _scrape(_T0, {alice: [_record("Alice Ng", "Mayor", council)]})

    vandalism = await _edit(vandal, PersonEdit(id=alice, fields={"name": "Rude Word"}))
    assert (await _roster())[alice].name == "Rude Word"

    await _scrape(datetime.now(timezone.utc), {alice: [_record("Alice Ng", "Mayor", council)]})
    assert (await _roster())[alice].name == "Rude Word", "a scrape does not overwrite a claim"

    await _roll_back(vandalism)

    assert (await _roster())[alice].name == "Alice Ng"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_9_one_changeset_rolls_back_together_through_three_levels_of_undo():
    council, school = await _organizations()
    alice, bob = _ids()
    editor = await _user("carol")
    await _scrape(_T0, {
        alice: [_record("Alice Ng", "Mayor", council)],
        bob: [_record("Bob Ito", "Board Member", school)],
    })
    council_post, school_post = await _post_of(council), await _post_of(school)

    edit = await _edit(editor, PersonEdit(
        id=alice,
        fields={"name": "Alice N.", "image": "https://zz-rollback-scenarios.gov/new.jpg"},
        offices=[OfficeEdit(id=council_post), OfficeEdit(id=school_post)],
    ))

    def edited(person: Person) -> bool:
        return (
            person.name == "Alice N."
            and person.image == "https://zz-rollback-scenarios.gov/new.jpg"
            and _organizations_of(person) == {council, school}
        )

    def original(person: Person) -> bool:
        return (
            person.name == "Alice Ng"
            and person.image == _PAGE_IMAGE
            and _organizations_of(person) == {council}
        )

    assert edited((await _roster())[alice])
    first = await _roll_back(edit)
    assert original((await _roster())[alice]), "the three claims roll back together"
    second = await _roll_back(first)
    assert edited((await _roster())[alice])
    await _roll_back(second)
    assert original((await _roster())[alice])

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM claims WHERE changeset_id::text = %s", (edit,)
        )
        assert await cur.fetchone() == (3,), "a rollback withdraws; it never deletes a claim"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_14_rolling_back_one_accounts_week_keeps_everyone_elses_work():
    council, _ = await _organizations()
    alice, bob = _ids()
    carol, dave, troll = await _user("carol"), await _user("dave"), await _user("troll")
    await _scrape(_T0, {
        alice: [_record("Alice Ng", "Mayor", council)],
        bob: [_record("Bob Ito", "Council Member", council)],
    })
    carols = await _edit(
        carol, PersonEdit(id=alice, fields={"image": "https://zz-rollback-scenarios.gov/c.jpg"})
    )

    await _edit(troll, PersonEdit(id=alice, fields={"name": "Rude Word"}))
    await _edit(troll, PersonEdit(id=bob, same_as=alice))
    await _edit(
        troll, PersonEdit(id=alice, fields={"image": "https://zz-rollback-scenarios.gov/rude.jpg"})
    )
    damaged = await _roster()
    assert set(damaged) == {alice}
    assert damaged[alice].name == "Rude Word"

    await _edit(
        dave, PersonEdit(id=alice, fields={"image": "https://zz-rollback-scenarios.gov/d.jpg"})
    )

    candidates = await rollback.list_user_changesets(troll)
    await rollback.rollback_changesets(
        [c.changeset_id for c in candidates if c.kind != ChangesetKind.ROLLBACK],
        SYSTEM_USER_ID,
        "profanity",
    )

    roster = await _on_roster()
    assert set(roster) == {alice, bob}
    assert roster[alice].name == "Alice Ng"
    assert roster[alice].image == "https://zz-rollback-scenarios.gov/d.jpg", "dave's later fix"
    assert _organizations_of(roster[bob]) == {council}
    for person_id in (alice, bob):
        assert await _membership_rows(person_id) == [(_T0, None)], (
            "no term ends at the troll's merge"
        )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM claims WHERE changeset_id::text = %s AND claim_is_live(id)",
            (carols,),
        )
        assert await cur.fetchone() == (1,), "carol's older fix is still underneath"
        await cur.execute(
            "SELECT count(*) FROM changesets WHERE jurisdiction_ocdid = %s AND kind = 'rollback'",
            (_OCDID,),
        )
        assert await cur.fetchone() == (3,)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_15_two_users_edit_one_field_and_are_rolled_back_in_turn():
    council, _ = await _organizations()
    alice, _ = _ids()
    carol, dave = await _user("carol"), await _user("dave")
    await _scrape(_T0, {alice: [_record("Alice Ng", "Mayor", council)]})

    carols = await _edit(carol, PersonEdit(id=alice, fields={"name": "Alice C."}))
    daves = await _edit(dave, PersonEdit(id=alice, fields={"name": "Alice D."}))
    assert (await _roster())[alice].name == "Alice D.", "the newest claim wins"

    carols_rollback = await _roll_back(carols)
    assert (await _roster())[alice].name == "Alice D.", "an outranked claim's rollback shows nothing"

    await _roll_back(daves)
    assert (await _roster())[alice].name == "Alice Ng", "back to the page, not to carol"

    await _roll_back(carols_rollback)
    assert (await _roster())[alice].name == "Alice C."


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_17_rolling_back_the_same_changeset_twice_writes_nothing():
    council, _ = await _organizations()
    alice, _ = _ids()
    scrape = await _scrape(_T0, {alice: [_record("Alice Ng", "Mayor", council)]})
    first = await _roll_back(scrape)
    assert await _roster() == {}

    with pytest.raises(rollback.NothingToRollBack):
        await rollback.rollback_changeset(scrape, SYSTEM_USER_ID, "again")

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM changesets WHERE jurisdiction_ocdid = %s AND kind = 'rollback'",
            (_OCDID,),
        )
        assert await cur.fetchone() == (1,)

    await _roll_back(first)
    assert set(await _on_roster()) == {alice}


async def _label_of(person_id: str) -> str | None:
    [membership] = (await _roster())[person_id].memberships
    return membership.label


@pytest.mark.asyncio
@pytest.mark.integration
async def test_clearing_a_label_says_there_is_none_and_rolling_that_back_restores_the_label():
    council, _ = await _organizations()
    alice, _ = _ids()
    carol, dave = await _user("carol"), await _user("dave")
    await _scrape(_T0, {alice: [_record("Alice Ng", "Council Member Place 3", council)]})
    post = await _post_of(council)

    await _edit(carol, PersonEdit(id=alice, offices=[OfficeEdit(id=post, membership_label="Chair")]))
    cleared = await _edit(dave, PersonEdit(id=alice, offices=[OfficeEdit(id=post, membership_label=None)]))
    assert await _label_of(alice) is None, "nothing, though the page says Place 3"

    await _roll_back(cleared)
    assert await _label_of(alice) == "Chair", "carol's value shows through again"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scenario_18_a_rollback_of_a_rollback_of_someone_elses_rollback():
    council, _ = await _organizations()
    alice, _ = _ids()
    carol = await _user("carol")
    await _scrape(_T0, {alice: [_record("Alice Ng", "Mayor", council)]})

    removal = await _edit(carol, PersonEdit(id=alice, offices=[]))
    first = await _roll_back(removal)
    second = await _roll_back(first)
    assert alice not in await _on_roster(), "carol's removal is in force again"

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT DISTINCT changeset_id::text FROM claims "
            "WHERE kind = 'withdraw' AND claim_is_live(id) AND changeset_id IN "
            "(SELECT id FROM changesets WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        assert await cur.fetchall() == [(second,)], "only the newest rollback's withdraws are live"

    await _roll_back(second)
    assert _organizations_of((await _on_roster())[alice]) == {council}
