"""A maintainer editing a live roster, outside any scrape.

Real Postgres: what this exists to prove is that the edit lands in the *database* — the whole
point of the change. Before 2026-08-26 this path patched the open-data YAML and wrote no rows,
so an edit was invisible here and the next scrape reverted it.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz', cleaned before/after.
"""

import datetime
import uuid

import pytest
import pytest_asyncio

import services.roster_edits as roster_edits
from core.people_edits import PeopleValidationError
from core.post_derivation import DerivedMembership
from database import divisions, memberships, organizations, posts
from core.people_edits import PersonPatch
from database.database import get_pool
from database.changeset_predicates import DISMISSED_SUPERSEDED
from database.dismissals import supersede_stacked_changesets
from database.source_records import insert_source_records
from services.roster import proposed_roster
from schemas.assertions import EntityType
from schemas.common import Identity, UserRole

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:editville/government"
_BASE = "ocd-division/country:us/state:zz/place:editville"
_EMAIL = "zz-editville-maintainer@example.com"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        # Changesets first: `changesets.organization_id` is a FK since 158, so an
        # organization cannot go while a changeset still names it.
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute(
            "DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM assertions WHERE entity_id IN "
            "(SELECT id FROM people WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        await cur.execute(
            "DELETE FROM source_records WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM users WHERE email = %s", (_EMAIL,))
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> tuple[str, Identity]:
    """One published person, and a maintainer to edit them."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, status) "
            "VALUES (%s, 'zz', 'local', 'active')",
            (_OCDID,),
        )
        # The changeset that published them. `people` rows only exist because
        # `publish_changeset` wrote them, so a fixture with a published person and no published
        # changeset is a state production cannot reach — and a hand edit now files under it
        # rather than minting one of its own.
        await cur.execute(
            "INSERT INTO changesets (kind, jurisdiction_ocdid, "
            "                        updated_at, published_at, created_at) "
            "VALUES ('scrape', %s, %s, now(), now()) "
            "ON CONFLICT DO NOTHING",
            (_OCDID, datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)),
        )
        await cur.execute(
            # `source_urls` and `updated_at` are required by `SubmittedPersonRecord`, which every
            # edit is validated against — a person without them fails before any field does.
            "INSERT INTO people "
            "  (id, jurisdiction_ocdid, name, phones, source_urls, updated_at, "
            "   other_names, emails, urls) "
            "VALUES (%s, %s, 'Ada Chen', ARRAY['(206) 555-0111'], "
            "        ARRAY['https://editville.gov/council'], now(), "
            "        ARRAY[]::text[], ARRAY[]::text[], ARRAY[]::text[])",
            (person_id, _OCDID),
        )
        # A seat, and an open membership in it: `get_roster` is "has an open membership", so
        # a person without one is not on the roster and the edit would read as an addition.
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await memberships.upsert(
            cur,
            DerivedMembership(person_id=person_id, source_labels=["Mayor"]),
            post_id,
            org,
            datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
        )
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'github', 'zz-maint', %s) RETURNING id::text",
            (_EMAIL, UserRole.MAINTAINERS.value),
        )
        row = await cur.fetchone()
        assert row is not None
        user_id = row[0]
        await conn.commit()
    return person_id, Identity(
        type="session",
        provider="github",
        provider_user_id="zz-maint",
        email=_EMAIL,
        role=UserRole.MAINTAINERS,
        user_id=user_id,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_edit_is_recorded_as_an_assertion_so_a_scrape_cannot_revert_it():
    """The reason this path changed. It used to write only the open-data file, so nothing said
    a human had chosen the value and the next publish overwrote it from the sightings."""
    person_id, user = await _seed()

    await roster_edits.edit_published(
        _OCDID,
        [PersonPatch(id=person_id, fields={"phones": ["(206) 555-0999"]})],
        user,
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # Every row, because `phones` is a list field: assertions on those key on the value,
        # so an edit leaves one per number rather than one per field.
        await cur.execute(
            "SELECT value::text FROM assertions "
            "WHERE entity_type = %s AND entity_id::text = %s AND field_path = 'phones'",
            (EntityType.PERSON.value, person_id),
        )
        values = [row[0] for row in await cur.fetchall()]
    assert values, "the edit left no assertion behind"
    assert any("555-0999" in value for value in values), values


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_edit_reaches_the_people_row_not_only_the_file():
    person_id, user = await _seed()

    await roster_edits.edit_published(
        _OCDID, [PersonPatch(id=person_id, fields={"name": "Ada M. Chen"})], user
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name FROM people WHERE id::text = %s", (person_id,))
        row = await cur.fetchone()
    assert row is not None and row[0] == "Ada M. Chen"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_edit_mints_a_changeset_born_published():
    """A hand edit is a bundle of changes to one jurisdiction, by one producer, at one time —
    a changeset. It needs to be one for its own timeline row, its own open-data commit url, its
    own author, and to supersede an older pending scrape.

    Born published, and it has to be: it writes `source_records` for anyone added, so a pending
    one would satisfy AVAILABLE_FOR_REVIEW and flash into the queue between the two writes.

    What it must *not* do is advance `last_seen_at` — that is `publish_changeset`'s rule, asserted
    separately below."""
    person_id, user = await _seed()

    changeset_id, _ = await roster_edits.edit_published(
        _OCDID, [PersonPatch(id=person_id, fields={"name": "Ada M. Chen"})], user
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            # No run: a hand edit is not an attempt, so nothing in `pipeline_runs` points here.
            "SELECT c.kind, c.published_at IS NOT NULL, c.updated_at IS NOT NULL, "
            "       NOT EXISTS (SELECT 1 FROM pipeline_runs r WHERE r.changeset_id = c.id) "
            "FROM changesets c WHERE c.id::text = %s",
            (changeset_id,),
        )
        assert await cur.fetchone() == ("people_edit", True, True, True)

@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_added_person_lands_in_the_seat_they_were_given():
    """The sighting carries the chosen post's label, so the ordinary derivation resolves the
    role from it. Recording only `post_id` left the label empty, no role matched, and they
    were published into the `unmatched` seat — which exists for labels we cannot parse, not
    for a question nobody asked the human who was right there."""
    _, user = await _seed()
    added_id = str(uuid.uuid4())

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        seat = await posts.find_or_create(cur, _OCDID, org, "clerk", _BASE)
        await conn.commit()

    await roster_edits.edit_published(
        _OCDID,
        [
            PersonPatch(
                id=added_id,
                fields={
                    "name": "Bo Nguyen",
                    "jurisdiction_ocdid": _OCDID,
                    "source_urls": ["https://editville.gov/clerk"],
                    "updated_at": "2026-08-26T00:00:00+00:00",
                    "post_id": seat,
                },
            )
        ],
        user,
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT sr.label FROM source_records sr "
            "JOIN source_record_identities i ON i.source_record_id = sr.id "
            "WHERE i.person_id::text = %s",
            (added_id,),
        )
        labels = [row[0] for row in await cur.fetchall()]
        await cur.execute(
            "SELECT p.role_id FROM memberships m JOIN posts p ON p.id = m.post_id "
            "WHERE m.person_id::text = %s",
            (added_id,),
        )
        roles = [row[0] for row in await cur.fetchall()]

    assert labels == ["Clerk"], labels
    assert roles == ["clerk"], roles


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_addition_with_no_seat_is_refused():
    """The editor asks for a post; this is what makes it a rule. The route is reachable
    without the editor, and a sighting with nothing to say would publish somebody into the
    `unmatched` seat."""
    _, user = await _seed()

    with pytest.raises(PeopleValidationError) as caught:
        await roster_edits.edit_published(
            _OCDID,
            [
                PersonPatch(
                    id=str(uuid.uuid4()),
                    fields={
                        "name": "Bo Nguyen",
                        "jurisdiction_ocdid": _OCDID,
                        "source_urls": ["https://editville.gov/clerk"],
                        "updated_at": "2026-08-26T00:00:00+00:00",
                    },
                )
            ],
            user,
        )

    assert caught.value.failures[0]["field"] == "post_id"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_addition_naming_a_post_that_is_gone_is_refused():
    """Same rule, reached differently: an id resolving to no post yields no label."""
    _, user = await _seed()

    with pytest.raises(PeopleValidationError):
        await roster_edits.edit_published(
            _OCDID,
            [
                PersonPatch(
                    id=str(uuid.uuid4()),
                    fields={
                        "name": "Bo Nguyen",
                        "jurisdiction_ocdid": _OCDID,
                        "source_urls": ["https://editville.gov/clerk"],
                        "updated_at": "2026-08-26T00:00:00+00:00",
                        "post_id": str(uuid.uuid4()),
                    },
                )
            ],
            user,
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_leaving_somebody_out_retires_them():
    """⚠️ `data` is the whole roster, not a list of changes. Publishing closes the membership
    of anyone absent from it — that is how removal works, and it is why a caller sending only
    the people it edited would retire everybody else.

    `buildPeoplePatch` maps over every current person for this reason. Pinned here because
    nothing in the signature says so and the failure is silent.
    """
    kept_id, user = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        other_id = str(uuid.uuid4())
        await cur.execute(
            "INSERT INTO people "
            "  (id, jurisdiction_ocdid, name, source_urls, updated_at, "
            "   other_names, emails, urls, phones) "
            "VALUES (%s, %s, 'Cy Okonkwo', ARRAY['https://editville.gov/council'], now(), "
            "        ARRAY[]::text[], ARRAY[]::text[], ARRAY[]::text[], ARRAY[]::text[])",
            (other_id, _OCDID),
        )
        org = await organizations.find_or_create(cur, _OCDID)
        seat = await posts.find_or_create(cur, _OCDID, org, "clerk", _BASE)
        await memberships.upsert(
            cur,
            DerivedMembership(person_id=other_id, source_labels=["Clerk"]),
            seat,
            org,
            datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
        )
        await conn.commit()

    # Only the mayor is sent. The clerk is absent, so their membership closes.
    await roster_edits.edit_published(
        _OCDID, [PersonPatch(id=kept_id, fields={"name": "Ada M. Chen"})], user
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT closed_at IS NOT NULL FROM memberships WHERE person_id::text = %s",
            (other_id,),
        )
        row = await cur.fetchone()
    assert row is not None and row[0] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_refused_edit_leaves_no_request_behind():
    """A born-published request that published nothing is worse than none: the sweep counts
    published requests as supersedors, so a phantom would dismiss every pending card."""
    _, user = await _seed()

    with pytest.raises(PeopleValidationError):
        await roster_edits.edit_published(
            _OCDID,
            [
                PersonPatch(
                    id=str(uuid.uuid4()),
                    fields={
                        "name": "Bo Nguyen",
                        "jurisdiction_ocdid": _OCDID,
                        "source_urls": ["https://editville.gov/clerk"],
                        "updated_at": "2026-08-26T00:00:00+00:00",
                    },
                )
            ],
            user,
        )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        row = await cur.fetchone()
    # One: the seeded scrape that published this roster. The guarantee used to need enforcing
    # because a refused edit could leave its own half-built changeset behind; now no edit ever
    # makes one, so there is nothing to leave.
    assert row is not None and row[0] == 1, "a refused edit registered a request"


async def _seed_second_person() -> str:
    """Somebody on the same roster that the edit does not touch."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO people "
            "  (id, jurisdiction_ocdid, name, phones, source_urls, updated_at, "
            "   other_names, emails, urls) "
            "VALUES (%s, %s, 'Bo Nguyen', ARRAY[]::text[], "
            "        ARRAY['https://editville.gov/clerk'], now(), "
            "        ARRAY[]::text[], ARRAY[]::text[], ARRAY[]::text[])",
            (person_id, _OCDID),
        )
        org = await organizations.find_or_create(cur, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "clerk", _BASE)
        await memberships.upsert(
            cur,
            DerivedMembership(person_id=person_id, source_labels=["Clerk"]),
            post_id,
            org,
            datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
        )
        await conn.commit()
    return person_id


async def _pending_scrape(updated_at: datetime.datetime) -> str:
    """A scrape awaiting review: a request with a run behind it and one sighting."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (kind, jurisdiction_ocdid, created_at, updated_at) "
            "VALUES ('scrape', %s, %s, %s) RETURNING id::text",
            (_OCDID, updated_at, updated_at),
        )
        row = await cur.fetchone()
        assert row is not None
        changeset_id = row[0]
        await cur.execute(
            "INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label, source_url) "
            "VALUES (%s, %s, 'Cy Okonkwo', 'Clerk', 'https://editville.gov/clerk')",
            (changeset_id, _OCDID),
        )
        await conn.commit()
    return changeset_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_hand_edit_supersedes_a_pending_scrape():
    """Deliberate: the edit is the newest word on the roster. Publishing the older scrape over
    it would retire anyone the edit added, and `_refuse_if_superseded` would refuse it anyway —
    so publishing dismisses it rather than leaving a card nobody can publish.

    This is what the edit's `updated_at = now()` buys, and why it keeps it even though the same
    column must not date a seat."""
    person_id, user = await _seed()
    scrape = await _pending_scrape(
        datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
    )

    await roster_edits.edit_published(
        _OCDID, [PersonPatch(id=person_id, fields={"name": "Ada M. Chen"})], user
    )

    # In the publish's own transaction, so there is nothing left for the sweep to find.
    assert await supersede_stacked_changesets() == []
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT dismissed_reason FROM changesets WHERE id::text = %s", (scrape,)
        )
        row = await cur.fetchone()
    assert row is not None and row[0] == DISMISSED_SUPERSEDED

@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_post_pick_survives_a_save_and_comes_back_scoped_to_its_organization():
    """A pick is a decision, and it has to outlive the save that recorded it.

    It did not: `post_id` was absent from `EDITABLE_FIELDS`, so `stated_from_edit` wrote no
    assertion and `with_stated_values` reapplied nothing. A reviewer could pick a post, save for
    later, come back, and publish into whatever the labels derived — their answer discarded
    without a word. Nothing covered `roster_edits.save` at all, which is how it survived.

    Picks are stored per post rather than per person, because a person holds one per
    organization. This seeds two bodies and asserts the roster reads back only the one the
    changeset is about, still as a single value: the reviewer is choosing one membership.
    """
    # The seeded person, not a fresh uuid: the wipe reaches assertions through `people`, so a
    # person who was never inserted leaves rows that block the user delete in teardown.
    person_id, user = await _seed()
    changeset_id = str(uuid.uuid4())

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        council = await organizations.find_or_create(cur, _OCDID, "Council")
        school_board = await organizations.find_or_create(cur, _OCDID, "School Board")
        await divisions.find_or_create(cur, _BASE, _OCDID)
        council_seat = await posts.find_or_create(cur, _OCDID, council, "clerk", _BASE)
        board_seat = await posts.find_or_create(cur, _OCDID, school_board, "clerk", _BASE)
        await conn.commit()

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets "
            "  (id, kind, jurisdiction_ocdid, updated_at, organization_id) "
            "VALUES (%s, 'scrape', %s, now(), %s)",
            (changeset_id, _OCDID, council),
        )
        await conn.commit()
    await insert_source_records(
        changeset_id,
        _OCDID,
        {
            person_id: [
                {
                    "name": "Bo Nguyen",
                    "label": "Clerk",
                    "source_url": "https://editville.gov/clerk",
                }
            ]
        },
    )

    for seat in (council_seat, board_seat):
        await roster_edits.save(
            changeset_id,
            _OCDID,
            [PersonPatch(id=person_id, fields={"post_id": seat})],
            user,
        )

    # Both picks are kept — one per body, neither overwriting the other.
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT value #>> '{}' FROM assertions "
            "WHERE entity_id = %s AND field_path = 'post_id' AND kind = 'accept'",
            (person_id,),
        )
        assert {row[0] for row in await cur.fetchall()} == {council_seat, board_seat}

    # The roster shows the one this changeset is about, as a single value.
    roster = await proposed_roster(changeset_id, _OCDID)
    assert [person["post_id"] for person in roster] == [council_seat]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_hand_edit_does_not_advance_last_seen_at():
    """The whole reason a hand edit's changeset is treated differently. `updated_at` on a
    `people_edit` is now(), so publishing one would otherwise claim the source still lists
    everyone it touched — `DATABASE.md` has `last_seen_at` as "advanced on every publish that
    still seats them", and a hand edit read nothing."""
    person_id, user = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT last_seen_at FROM memberships "
            " WHERE person_id = %s AND closed_at IS NULL",
            (person_id,),
        )
        before = (await cur.fetchone())[0]

    await roster_edits.edit_published(
        _OCDID, [PersonPatch(id=person_id, fields={"name": "Ada M. Chen"})], user
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT last_seen_at FROM memberships "
            " WHERE person_id = %s AND closed_at IS NULL",
            (person_id,),
        )
        after = (await cur.fetchone())[0]

    assert after == before, "a hand edit advanced last_seen_at"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_only_the_edited_person_gets_a_new_updated_at():
    """`PERSON_UPSERT` writes the whole roster on every publish, so without the `DO UPDATE`'s
    `WHERE … IS DISTINCT FROM …` every person would get a fresh `updated_at` whenever anyone
    was touched — and the published file would diff for people nobody changed.

    Postgres evaluates that predicate per conflicting row, so this needs no bookkeeping; the
    test exists so the WHERE is not removed as redundant."""
    edited_id, user = await _seed()
    untouched_id = await _seed_second_person()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, updated_at FROM people WHERE jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        before = {row[0]: row[1] for row in await cur.fetchall()}

    await roster_edits.edit_published(
        _OCDID, [PersonPatch(id=edited_id, fields={"name": "Ada M. Chen"})], user
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, updated_at FROM people WHERE jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        after = {row[0]: row[1] for row in await cur.fetchall()}

    assert after[edited_id] > before[edited_id], "the edited person kept a stale updated_at"
    assert after[untouched_id] == before[untouched_id], "an untouched person was restamped"
