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

from core.people_edits import PeopleValidationError
from core.post_derivation import DerivedMembership, MembershipSource
from database import divisions, memberships, organizations, posts
from database.database import get_pool
from schemas.jurisdictions import OfficeEdit, PersonEdit
from services.roster_edits import UnknownPost, edit_published_roster
from database.changeset_predicates import DISMISSED_SUPERSEDED
from database.dismissals import supersede_stacked_changesets
from database.source_records import insert_source_records
from schemas.claims import EntityType
from schemas.common import Identity, UserRole
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:editville/government"
_BASE = "ocd-division/country:us/state:zz/place:editville"
_EMAIL = "zz-editville-maintainer@example.com"


async def _wipe():
    """In dependency order: claims, then the changesets they point at (which takes their source
    records with them), then the organizations those records named, then the rest."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        # A membership claim's entity is `uuid5(person, post)` and it may carry no changeset,
        # so "the claims about these people" catches neither: take everything this maintainer
        # said, whatever it was about.
        await cur.execute(
            "DELETE FROM claims WHERE created_by IN "
            "(SELECT id FROM users WHERE email = %s) "
            "   OR entity_id IN (SELECT id FROM people WHERE jurisdiction_ocdid = %s)",
            (_EMAIL, _OCDID),
        )
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute(
            "DELETE FROM source_records WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (_OCDID,))
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
            "RETURNING id::text",
            (_OCDID, datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)),
        )
        changeset_row = await cur.fetchone()
        assert changeset_row is not None
        scrape_id = changeset_row[0]
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
        await factories.bind_membership(
            cur,
            DerivedMembership(person_id=person_id, sources=[MembershipSource(note="Mayor")]),
            post_id,
            org,
            datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
        )
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'github', 'zz-maint', %s, %s) RETURNING id::text",
            (_EMAIL, _EMAIL.replace("@", "-"), UserRole.MAINTAINERS.value),
        )
        row = await cur.fetchone()
        assert row is not None
        user_id = row[0]
        await conn.commit()
    # The record behind the row, under the scrape that published it: to the fold a person is
    # their records.
    await insert_source_records(
        scrape_id,
        _OCDID,
        {
            person_id: [
                {
                    "name": "Ada Chen",
                    "label": "Mayor",
                    "source_url": "https://editville.gov/council",
                    "url": "https://editville.gov/council",
                    "organization_id": org,
                    "phone": "(206) 555-0111",
                }
            ]
        },
    )
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE source_records SET created_at = %s WHERE changeset_id = %s",
            (datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc), scrape_id),
        )
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

    await edit_published_roster(
        _OCDID,
        [PersonEdit(id=person_id, fields={"phones": ["(206) 555-0999"]})],
        user.user_id,
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # Every row, because `phones` is a list field: claims on those key on the value,
        # so an edit leaves one per number rather than one per field.
        await cur.execute(
            "SELECT value::text FROM claims "
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

    await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})], user.user_id
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

    What it must *not* do is reopen the membership, claimed separately below."""
    person_id, user = await _seed()

    changeset_id = await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})], user.user_id
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
async def test_an_addition_with_no_office_puts_nobody_on_the_roster():
    """This test verified that an addition with no post was refused, because a sighting with
    nothing to say would have published somebody into the `unmatched` seat. It now verifies
    that nothing lands: being on the roster is holding an office, so an addition that names
    none says a person exists and places them nowhere."""
    _, user = await _seed()
    added_id = str(uuid.uuid4())

    if True:
        await edit_published_roster(
            _OCDID,
            [
                PersonEdit(
                    id=added_id,
                    fields={
                        "name": "Bo Nguyen",
                        "jurisdiction_ocdid": _OCDID,
                        "source_urls": ["https://editville.gov/clerk"],
                    },
                )
            ],
            user.user_id,
        )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM memberships WHERE person_id::text = %s",
            (added_id,),
        )
        assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_addition_naming_a_post_that_is_gone_is_refused():
    """Same rule, reached differently. This test verified a `PeopleValidationError`, raised
    when the addition's `post_id` resolved to no label. It now verifies `UnknownPost`, the
    route's own guard, because the fold ignores a claim naming a post it cannot find."""
    _, user = await _seed()

    with pytest.raises(UnknownPost):
        await edit_published_roster(
            _OCDID,
            [
                PersonEdit(
                    id=str(uuid.uuid4()),
                    fields={
                        "name": "Bo Nguyen",
                        "jurisdiction_ocdid": _OCDID,
                        "source_urls": ["https://editville.gov/clerk"],
                    },
                    offices=[OfficeEdit(id=str(uuid.uuid4()))],
                )
            ],
            user.user_id,
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
        await factories.bind_membership(
            cur,
            DerivedMembership(person_id=other_id, sources=[MembershipSource(note="Clerk")]),
            seat,
            org,
            datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
        )
        await conn.commit()

    # Only the mayor is sent. The clerk is absent, so their membership closes.
    await edit_published_roster(
        _OCDID, [PersonEdit(id=kept_id, fields={"name": "Ada M. Chen"})], user.user_id
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM memberships WHERE person_id::text = %s", (other_id,)
        )
        row = await cur.fetchone()
    # This test verified that the absent person's membership was closed. It now verifies that
    # they hold none, because the editor's removal files an `exists` reject and the writer
    # derives the roster without it rather than closing a row.
    assert row is not None and row[0] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_refused_edit_leaves_no_request_behind():
    """A born-published request that published nothing is worse than none: the sweep counts
    published requests as supersedors, so a phantom would dismiss every pending card."""
    _, user = await _seed()

    # This test refused on a missing `post_id`; it now refuses on one that names no post,
    # which is the guard the edit route carries.
    with pytest.raises(UnknownPost):
        await edit_published_roster(
            _OCDID,
            [
                PersonEdit(
                    id=str(uuid.uuid4()),
                    fields={
                        "name": "Bo Nguyen",
                        "jurisdiction_ocdid": _OCDID,
                        "source_urls": ["https://editville.gov/clerk"],
                    },
                    offices=[OfficeEdit(id=str(uuid.uuid4()))],
                )
            ],
            user.user_id,
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
        await factories.bind_membership(
            cur,
            DerivedMembership(person_id=person_id, sources=[MembershipSource(note="Clerk")]),
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
        organization_id = await factories.default_organization(cur, _OCDID)
        await cur.execute(
            "INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label, source_url, organization_id, person_id) "
            "VALUES (%s, %s, 'Cy Okonkwo', 'Clerk', 'https://editville.gov/clerk', %s, gen_random_uuid())",
            (changeset_id, _OCDID, organization_id),
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

    await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})], user.user_id
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
async def test_a_hand_edit_does_not_reopen_the_membership():
    """A name edit changes the person, not the period they hold the post. This checked that
    `last_seen_at` did not move; that column went at 228, so it now checks the row keeps its
    `opened_at`, which a rebuild that re-dated the period would move."""
    person_id, user = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT opened_at FROM memberships "
            " WHERE person_id = %s AND closed_at IS NULL",
            (person_id,),
        )
        before = (await cur.fetchone())[0]

    await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})], user.user_id
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT opened_at FROM memberships "
            " WHERE person_id = %s AND closed_at IS NULL",
            (person_id,),
        )
        after = (await cur.fetchone())[0]

    assert after == before, "a hand edit reopened the membership"


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

    await edit_published_roster(
        _OCDID, [PersonEdit(id=edited_id, fields={"name": "Ada M. Chen"})], user.user_id
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, updated_at FROM people WHERE jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        after = {row[0]: row[1] for row in await cur.fetchall()}

    assert after[edited_id] > before[edited_id], "the edited person kept a stale updated_at"
    assert after[untouched_id] == before[untouched_id], "an untouched person was restamped"


async def _activity_rows(changeset_id: str) -> list[tuple]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type, changes FROM activity WHERE changeset_id::text = %s ORDER BY type",
            (changeset_id,),
        )
        return await cur.fetchall()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_hand_edit_keeps_a_post_that_was_assigned():
    """Crescent City, 2026-09-18: the editor assigns a post, then saves person fields. The save
    re-derived everyone's post from label text; an assigned membership has no sources, so it
    derived to nothing and was closed as absent."""
    person_id, user = await _seed()
    clerk = await _clerk_post()

    await _seat(person_id, clerk, None, user.user_id)
    await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})], user.user_id
    )

    assert await _open_posts(person_id) == [clerk]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_hand_edit_does_not_re_derive_a_post_from_label_text():
    """The other half: someone held a post their source label does not parse to (a reviewer
    picked it). Saving their fields moved them to the parsed post."""
    person_id, user = await _seed()
    clerk = await _clerk_post()
    await _seat(person_id, clerk, None, user.user_id)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE memberships SET sources = %s::jsonb "
            "WHERE person_id::text = %s AND closed_at IS NULL",
            ('[{"url": null, "note": "Mayor"}]', person_id),
        )
        await conn.commit()

    await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})], user.user_id
    )

    assert await _open_posts(person_id) == [clerk]


async def _seat(person_id: str, post_id: str, label: str | None, user_id: str) -> None:
    """Put somebody in an office. Was `memberships.assign`, deleted 2026-09-23."""
    await edit_published_roster(
        _OCDID,
        [PersonEdit(id=person_id, offices=[OfficeEdit(id=post_id, membership_label=label)])],
        user_id,
    )


async def _clerk_post() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "clerk", _BASE)
        await conn.commit()
    return post_id


async def _open_posts(person_id: str) -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT post_id::text FROM memberships "
            "WHERE person_id::text = %s AND closed_at IS NULL",
            (person_id,),
        )
        return [row[0] for row in await cur.fetchall()]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_edit_is_reported_from_what_the_rebuild_changed():
    """9d. Replaces the two tests dropped when `edit_published` went, which claimed the same
    rows from a diff of the *payload*. The feed now reads the roster before against the roster
    after, so it reports what actually changed rather than what was asked for."""
    person_id, user = await _seed()

    changeset_id = await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})], user.user_id
    )

    rows = await _activity_rows(changeset_id)
    edits = [changes for type_, changes in rows if type_ == "edit_person"]
    assert len(edits) == 1, [type_ for type_, _ in rows]
    assert edits[0]["entity_id"] == person_id
    # Two fields, though the edit named one: renaming moves the name the records carry into
    # `other_names`. A diff of the payload could not see that, which is why this reads the
    # rosters.
    fields = {field["field"]: field["after"] for field in edits[0]["fields"]}
    assert fields["name"] == "Ada M. Chen"
    assert "Ada Chen" in fields["other_names"]
