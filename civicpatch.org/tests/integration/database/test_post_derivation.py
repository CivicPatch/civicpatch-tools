"""Integration tests for the posts/memberships derivation.

Real Postgres because every guarantee here is a constraint or an ON CONFLICT clause, not
Python: match-or-mint is one statement, "one open membership per body" is a partial unique
index, and "a match writes nothing" is only true because the conflict path has no SET.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz', cleaned before/after.
"""

import datetime
import json
import uuid

import pytest
import pytest_asyncio

from core.people_edits import POSTS_FIELD
from core.post_derivation import ChosenPost, DerivedMembership
from core.roster_changes import ChangeKind, changes_of
from database import claims, divisions, memberships, organizations, posts
from database.users import SYSTEM_USER_ID
from database.database import get_pool
from database.review_priority import issue_count, issue_priority
from database.source_records import insert_source_records
from schemas.claims import Claim, ClaimKind, DefaultNote, EntityType, Source
from services.roster import card_sides
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:testville/government"
_BASE = "ocd-division/country:us/state:zz/place:testville"
_CURATOR = "zz-post-derivation-curator@example.com"
_WARD_3 = f"{_BASE}/ward:3"

_T0 = datetime.datetime(2026, 3, 11, tzinfo=datetime.timezone.utc)
_T1 = datetime.datetime(2026, 6, 2, tzinfo=datetime.timezone.utc)
_T2 = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            DELETE FROM memberships m USING posts p
            WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s
            """,
            (_OCDID,),
        )
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        # Changesets first: their source records point at organizations (205: ON DELETE RESTRICT),
        # so a body cannot go while a changeset's evidence still names it.
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
        # Before the jurisdictions themselves: `requests.jurisdiction_ocdid` is a FK, and
        # test_publish_writes_memberships_for_the_roster leaves a request behind. Without
        # this the wipe raises at *setup* of every test in the file, so one leftover row
        # takes the whole module down — and takes new breakage with it, silently.
        # `source_records` and `pipeline_runs` cascade from the request.
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        # The curator, and the claims pointing at them. `created_by` is a FK, so the user
        # cannot go first — and `claims` has none to memberships, so its rows outlive the
        # memberships they describe and would otherwise accumulate across runs.
        await cur.execute(
            "DELETE FROM claims WHERE created_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_CURATOR,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_CURATOR,))
        # Otherwise `add_post` rows survive the run and the mint counts below climb.
        await cur.execute(
            "DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


_ROSTER_URL = "https://zz.gov/roster"


async def _seed_person(name: str = "Test Person", urls: list[str] | None = None):
    """A real `people` row, because memberships.person_id is a FK to it."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, status)
            VALUES (%s, 'zz', 'local', %s, 'active')
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (_OCDID, json.dumps({})),
        )
        # Real jurisdictions get their default organization at sync time (open_data.py); this
        # raw insert bypasses that, so it has to do the pairing itself.
        await cur.execute(
            """
            INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, 'Government')
            ON CONFLICT (jurisdiction_ocdid, name) DO NOTHING
            """,
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name, urls) "
            "VALUES (%s, %s, %s, %s)",
            (person_id, _OCDID, name, urls or []),
        )
        await conn.commit()
    return person_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_record_mints_once_then_matches():
    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)

        first = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        second = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        assert first == second

        await cur.execute("SELECT count(*) FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        assert (await cur.fetchone())[0] == 1

        # A scrape proposes; it does not assert. 121 dropped `status` — a post is endorsed
        # exactly when it has a member, since memberships are only written at publish.
        await cur.execute("SELECT count(*) FROM memberships WHERE post_id = %s", (first,))
        assert (await cur.fetchone())[0] == 0
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_match_never_overwrites_a_human_edit():
    """The reason `DO NOTHING` is not `DO UPDATE`: headcount and tracking are human-owned, and
    the derivation has no update path to reach them."""
    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "council-member", _BASE, headcount=1)

        await cur.execute(
            "UPDATE posts SET meta_headcount = %s, meta_is_tracked = %s WHERE id = %s",
            (9, False, post_id),
        )
        await posts.find_or_create(cur, _OCDID, org, "council-member", _BASE, headcount=1)

        await cur.execute(
            "SELECT meta_headcount, meta_is_tracked FROM posts WHERE id = %s", (post_id,)
        )
        assert await cur.fetchone() == (9, False)
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_same_post_advances_the_window_without_a_second_row():
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        first = await factories.bind_membership(cur, DerivedMembership(person_id=person_id), post_id, org, _T0)
        second = await factories.bind_membership(cur, DerivedMembership(person_id=person_id), post_id, org, _T1)
        assert first == second

        await cur.execute(
            "SELECT first_seen_at, last_seen_at FROM memberships WHERE id = %s", (first,)
        )
        assert await cur.fetchone() == (_T0, _T1)
        await conn.rollback()


async def _already_published() -> None:
    """Put the jurisdiction past its first publish, by holding a seat that is not under test.

    A membership only exists at publish, so one is the proof — which is why the predicate reads
    memberships rather than `requests.published_at`. A *different* post on purpose: the tests
    below assert that the post they created is still unverified.
    """
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        other = await posts.find_or_create(cur, _OCDID, org, "clerk", _BASE)
        await factories.bind_membership(cur, DerivedMembership(person_id=person_id), other, org, _T0)
        await conn.commit()


async def _seed_request() -> str:
    changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, status)
            VALUES (%s, 'zz', 'local', %s, 'active')
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (_OCDID, json.dumps({})),
        )
        # Real jurisdictions get their default organization at sync time (open_data.py); this
        # raw insert bypasses that, so it has to do the pairing itself.
        await cur.execute(
            """
            INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, 'Government')
            ON CONFLICT (jurisdiction_ocdid, name) DO NOTHING
            """,
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind) "
            "VALUES (%s, %s, 'people_edit')",
            (changeset_id, _OCDID),
        )
        await conn.commit()
    return changeset_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_post_is_unverified_until_a_publish_puts_somebody_in_it():
    """Ingest mints the post; only publish writes the membership. The gap between them is
    exactly the window in which nobody has answered for the office a scrape invented.

    Now needs `_already_published`: the same claim held before, but it is only *reported* once
    the jurisdiction has been published at least once — see the suppression test below."""
    person_id = await _seed_person()
    await _already_published()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        unverified = await posts.unverified_by_jurisdiction(cur, [_OCDID])
        assert [post["id"] for post in unverified[_OCDID]] == [post_id]

        await factories.bind_membership(cur, DerivedMembership(person_id=person_id), post_id, org, _T0)
        assert await posts.unverified_by_jurisdiction(cur, [_OCDID]) == {_OCDID: []}
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unverified_post_raises_the_queue_score_and_the_badge():
    """A post nobody has vouched for is the one issue the queue can see for itself — the five
    roster checks are computed at read from two rosters SQL cannot derive. Without this the
    badge reads `0 issues` over a card that opens with one.

    Evaluated against a literal jurisdiction rather than an inserted request: the review pool
    is shared, and a spare request for this jurisdiction would reach unrelated tests.

    Needs `_already_published` for the same reason the card-side test does — the queue counts
    on the same two predicates, deliberately, so a card and its badge cannot disagree about
    whether there is anything to look at.
    """
    await _seed_person()  # for the jurisdiction row the organization FK needs
    await _already_published()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        await cur.execute(
            f"SELECT {issue_count('t.ocdid')}, {issue_priority('t.ocdid')} "
            "FROM (VALUES (%s)) t(ocdid)",
            (_OCDID,),
        )
        count, priority = await cur.fetchone()
        assert count == 1, "an unanswered post is an issue even with nothing else wrong"
        assert priority > 0, "and it must not sort as though it had nothing to review"
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_jurisdiction_with_no_unverified_posts_still_gets_a_key():
    """The review queue indexes the result by ocdid. A missing key would be a KeyError on the
    jurisdictions that are fine, which is most of them."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await posts.unverified_by_jurisdiction(cur, [_OCDID]) == {_OCDID: []}
        assert await posts.unverified_by_jurisdiction(cur, []) == {}
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unmatched_people_share_one_post_per_division():
    """No special case in code: an unresolvable label resolves to the `unmatched` role and
    the jurisdiction's own division, so everyone lands on the same post by the key alone."""
    first_person = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) "
            "VALUES (%s, %s, %s)",
            (second := str(uuid.uuid4()), _OCDID, "Other"),
        )
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)

        bucket = await posts.find_or_create(cur, _OCDID, org, "unmatched", _BASE)
        again = await posts.find_or_create(cur, _OCDID, org, "unmatched", _BASE)
        assert bucket == again

        await factories.bind_membership(
            cur, DerivedMembership(person_id=first_person, meta_unmatched_text=["Town Moderator"]), bucket, org, _T0
        )
        await factories.bind_membership(
            cur, DerivedMembership(person_id=second, meta_unmatched_text=["Supervisor of the Checklist"]), bucket, org, _T0
        )

        await cur.execute(
            "SELECT meta_unmatched_text FROM memberships WHERE post_id = %s ORDER BY meta_unmatched_text",
            (bucket,),
        )
        assert [row[0] for row in await cur.fetchall()] == [
            ["Supervisor of the Checklist"],
            ["Town Moderator"],
        ]
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publish_writes_memberships_for_the_roster():
    """The publish half end to end: the posts the records name are minted, the memberships
    opened, and the person row written.

    This test used to hand publish a roster and a derivation. It now stores the record and
    publishes the changeset, because publish takes neither: the fold derives both from the
    facts, including the term dates the page stated.
    """
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.get_default(cur, _OCDID)
    changeset_id = await _published_changeset(_T0)
    await insert_source_records(
        changeset_id,
        _OCDID,
        {
            person_id: [
                {
                    "name": "Robert Michaud",
                    "label": "Mayor",
                    "source_url": "https://example.gov",
                    "url": "https://example.gov",
                    "organization_id": organization_id,
                    # Partial on purpose: `start_date` was a `date` column until 144 and could
                    # not have held a bare year.
                    "start_date": "2025",
                    "end_date": "2029-12-31",
                }
            ]
        },
    )
    await _date_records(changeset_id, _T0)
    from database.publications import publish_changeset

    assert await publish_changeset(changeset_id, _OCDID) == 1

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT p.role_id, m.first_seen_at, m.closed_at, m.start_date, m.end_date
            FROM memberships m JOIN posts p ON p.id = m.post_id
            WHERE p.jurisdiction_ocdid = %s
            """,
            (_OCDID,),
        )
        rows = await cur.fetchall()
        assert len(rows) == 1
        role_id, first_seen_at, closed_at, start_date, end_date = rows[0]
        assert role_id == "mayor"
        assert closed_at is None
        # The record's own date, not the moment publish ran.
        assert first_seen_at == _T0
        # Valid time, what the source claims about the term, beside transaction time above.
        assert (start_date, end_date) == ("2025", "2029-12-31")

        await cur.execute(
            "SELECT name, source_urls, emails FROM people WHERE id = %s", (person_id,)
        )
        name, source_urls, emails = await cur.fetchone()
        assert name == "Robert Michaud"
        assert source_urls == ["https://example.gov"]
        assert emails == [], "a person with no emails has none, not NULL"

    # Asserted through the reader the jurisdiction modal actually calls, because the failure
    # mode is not an exception: it is a subtitle that silently goes blank.
    from database.people import get_person_models

    roster = await get_person_models(_OCDID)
    assert len(roster) == 1
    held = roster[0].memberships[0]
    assert held.role_id == "mayor"
    assert held.division_ocdid == _BASE
    # The source's own words, which is what `office.name` always was.
    assert held.source_labels == ["Mayor"]


# --- human writes: create, update, delete ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_returns_none_when_the_identity_is_taken():
    """The caller needs to tell "created" from "already there" apart to answer 409."""
    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)

        first = await posts.create_if_absent(cur, _OCDID, org, "mayor", _BASE)
        assert first is not None
        assert await posts.create_if_absent(cur, _OCDID, org, "mayor", _BASE) is None
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_human_created_post_is_matched_by_a_later_scrape():
    """Creating and minting produce the same row — identity is the triple, not the origin."""
    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)

        created = await posts.create_if_absent(cur, _OCDID, org, "mayor", _BASE, headcount=3)
        matched = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        assert created == matched
        await cur.execute("SELECT meta_headcount FROM posts WHERE id::text = %s", (created,))
        assert (await cur.fetchone())[0] == 3  # the scrape did not overwrite it
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_refuses_a_post_that_has_ever_been_held():
    """Held means history, including closed memberships — that is what keeps the timeline
    answerable. Unheld means a scrape proposed it and nobody endorsed it."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        held = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        unheld = await posts.find_or_create(cur, _OCDID, org, "clerk", _BASE)
        await factories.bind_membership(cur, DerivedMembership(person_id=person_id), held, org, _T0)

        assert await posts.delete_if_unheld(cur, held) is False
        assert await posts.delete_if_unheld(cur, unheld) is True
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_reaches_the_two_human_fields_and_reports_a_miss():
    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "trustee", _BASE)

        assert await posts.update_human_fields(cur, post_id, 5, False) is True
        await cur.execute(
            "SELECT meta_headcount, meta_is_tracked FROM posts WHERE id::text = %s", (post_id,)
        )
        assert await cur.fetchone() == (5, False)

        assert (
            await posts.update_human_fields(
                cur, "00000000-0000-0000-0000-000000000000", 1, True
            )
            is False
        )
        await conn.rollback()


async def _human_sets_label(cur, membership_id: str, label: str) -> None:
    """What `assign` does. `set_membership_label` with a user is the whole human edit: the value and the
    assertion saying somebody chose it, which is what survives the next scrape."""
    # `claims.created_by` is a foreign key, so an assertion needs somebody to have made it.
    await cur.execute(
        "INSERT INTO users (email, provider, provider_user_id, username, role) "
        "VALUES (%s, 'email', %s, %s, 'admins') RETURNING id::text",
        (_CURATOR, _CURATOR, _CURATOR.replace("@", "-")),
    )
    curator_id = (await cur.fetchone())[0]

    await memberships.set_membership_label(cur, membership_id, label, curator_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_membership_read_still_selects_every_column_it_names():
    """122 dropped `label` while this query still selected it, and only the absence of a caller
    hid that for two migrations. Executing it is the check."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await factories.bind_membership(cur, DerivedMembership(person_id=person_id), post_id, org, _T0)

        rows = await memberships.list_for_jurisdiction(cur, _OCDID)
        assert len(rows) == 1
        assert rows[0]["role_id"] == "mayor"
        assert rows[0]["label"] is None
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_label_naming_two_offices_keeps_the_loser_on_the_membership():
    """One open membership per person per organization means one role must define the post.
    Without somewhere for the other to land it was simply dropped: a clerk who is also
    treasurer published as a clerk, and the treasurership vanished.

    This test drove the two writes by hand. It now publishes the labels that carry them,
    because the fold parses the extra roles out of the page's own words."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)

    await _publish((org, person_id, "Clerk and Treasurer"))
    assert await _extra_roles(person_id) == ["treasurer"]

    # Derived from the label, so the newest scrape's answer is the whole answer: a role the
    # page stopped naming must not linger.
    await _publish((org, person_id, "Clerk"), at=_T1)
    assert await _extra_roles(person_id) == []


async def _extra_roles(person_id: str) -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT r.role_id FROM membership_roles r "
            "JOIN memberships m ON m.id = r.membership_id "
            "WHERE m.person_id = %s ORDER BY r.role_id",
            (person_id,),
        )
        return [row[0] for row in await cur.fetchall()]


async def _add_post_logs(changeset_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changes, user_id FROM activity "
            "WHERE type = 'add_post' AND changeset_id = %s",
            (changeset_id,),
        )
        return [{"changes": row[0], "user_id": row[1]} for row in await cur.fetchall()]


async def _mint(identities: list[tuple[str, str]], changeset_id: str) -> None:
    """Create posts the way publishing does, as (role_id, division_ocdid) in the default body."""
    from core.post_derivation import DerivedPost

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.get_default(cur, _OCDID)
        derived = [
            DerivedPost(
                organization_id=organization_id,
                role_id=role_id,
                role_label=role_id.title(),
                division_ocdid=division_ocdid,
                headcount=1,
                members=[],
            )
            for role_id, division_ocdid in identities
        ]
        await posts.create_all(cur, _OCDID, derived, changeset_id)
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_minting_a_post_is_logged_against_the_scrape_that_caused_it():
    """"Publishing this roster created a seat" is the event a reviewer needs told about, and it
    is answered from the log rather than a column on `posts` — creation happens once and never
    changes, so it is an event, not a property of the row."""
    changeset_id = await _seed_request()

    await _mint([("mayor", _BASE)], changeset_id)

    logs = await _add_post_logs(changeset_id)
    assert len(logs) == 1
    assert logs[0]["changes"]["subject"] == "mayor"
    # The system, not a person: nobody claimed this, a scrape did it. Since 160 that is said
    # by naming the system user rather than by leaving the column null.
    assert str(logs[0]["user_id"]) == SYSTEM_USER_ID


@pytest.mark.asyncio
@pytest.mark.integration
async def test_matching_an_existing_post_logs_nothing():
    """Only a mint is news. A second scrape seeing the same seat has invented nothing, and
    logging it would make every re-scrape look like a change."""
    first = await _seed_request()
    await _mint([("mayor", _BASE)], first)

    second = await _seed_request()
    await _mint([("mayor", _BASE)], second)

    assert len(await _add_post_logs(first)) == 1
    assert await _add_post_logs(second) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_only_the_new_seat_is_logged_when_a_scrape_mixes_both():
    changeset_id = await _seed_request()
    await _mint([("mayor", _BASE)], changeset_id)

    later = await _seed_request()
    await _mint([("mayor", _BASE), ("council-member", _WARD_3)], later)

    logs = await _add_post_logs(later)
    assert [log["changes"]["subject"] for log in logs] == ["council-member"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_jurisdictions_first_scrape_raises_no_post_issues():
    """Every seat is new on a first scrape, so one issue per seat says nothing a reviewer
    cannot see by reading the roster in front of them — it only buries the checks that do
    carry information. Onboarding a state (#2424, #2462) is entirely first scrapes.
    """
    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await conn.commit()

    async with pool.connection() as conn, conn.cursor() as cur:
        assert await posts.unverified_by_jurisdiction(cur, [_OCDID]) == {_OCDID: []}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_same_post_raises_once_the_jurisdiction_has_been_published():
    """The suppression is about the jurisdiction's first scrape, not about the post. Once
    anything here has been published, a seat nobody has vouched for is a real signal again —
    and this is the pair that proves the first test is not passing for some other reason."""
    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await conn.commit()

    await _already_published()

    async with pool.connection() as conn, conn.cursor() as cur:
        unverified = await posts.unverified_by_jurisdiction(cur, [_OCDID])
        assert [post["id"] for post in unverified[_OCDID]] == [post_id]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unreviewed_scrape_leaves_published_memberships_alone():
    """The point of retiring and re-dating memberships at publish and nowhere else.

    Ingest used to do both, so a scrape that fetched three of seven pages closed four
    memberships with nobody in the way. It was defended as observation — "the source stopped
    listing D" is true whether or not D left office — which holds for a good scrape and not
    for a bad one, and nothing at ingest can tell which.

    Asserted through `_apply_scrape_changes`, which is what ingest actually runs: the old
    tests called the writes directly and so stayed green when ingest stopped calling them.
    """
    from core.post_derivation import DerivedMembership
    from services.people_collector import _apply_scrape_changes

    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await factories.bind_membership(cur, DerivedMembership(person_id=person_id), post_id, org, _T0)
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind) "
            "VALUES (%s, %s, 'scrape')",
            (changeset_id := str(uuid.uuid4()), _OCDID),
        )
        # The run too: `_apply_scrape_changes` swallows its own errors, so without this the
        # old close-at-ingest path would raise on the missing run and this test would pass
        # against the very behaviour it exists to forbid.
        await cur.execute(
            "UPDATE changesets SET "
            "created_at = %s, updated_at = %s WHERE id = %s",
            (_T1, _T1, changeset_id),
        )
        await conn.commit()

    # A scrape naming somebody else entirely: the seated person is absent from it. Expressed
    # as a sighting rather than a derived post, because `_apply_scrape_changes` now reads the
    # scrape back through `proposed_roster` instead of being handed a derivation.
    other_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        await cur.execute(
            "INSERT INTO source_records "
            "  (changeset_id, jurisdiction_ocdid, name, label, source_url, organization_id) "
            "VALUES (%s, %s, 'Someone Else', 'Clerk', 'https://zz.gov/clerk', %s) RETURNING id",
            (changeset_id, _OCDID, organization_id),
        )
        await cur.execute(
            "INSERT INTO source_record_identities (source_record_id, person_id) "
            "VALUES (%s, %s)",
            ((await cur.fetchone())[0], other_id),
        )
        await conn.commit()

    await _apply_scrape_changes(changeset_id, _OCDID)

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT closed_at, last_seen_at FROM memberships WHERE person_id = %s",
            (person_id,),
        )
        closed_at, last_seen_at = await cur.fetchone()
    assert closed_at is None, "an unreviewed scrape closed a published membership"
    assert last_seen_at == _T0, "an unreviewed scrape moved a published last_seen_at"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_scrape_that_re_confirms_the_roster_publishes_and_moves_last_seen_at():
    """The complement of the test above, and the thing that was silently broken.

    A scrape proposing nothing new used to be dismissed as `unchanged`, so `publish_changeset`
    never ran and `last_seen_at` never moved — leaving it frozen at the last scrape that
    *changed* something. Ellensburg read 2025-06-22 after a 2026-09 scrape saw all fourteen of
    its people on the page.

    Re-confirmation is the one case where "we still see them" is the only thing the scrape has
    to say, and it was the one case that recorded nothing.
    """
    from core.post_derivation import DerivedMembership
    from services.people_collector import _apply_scrape_changes

    # Three, because `MIN_EXPECTED_PEOPLE` is 3: a one-person roster is itself a review issue,
    # and the gate would rightly refuse it.
    seats = [("mayor", "Mayor"), ("clerk", "Clerk"), ("treasurer", "Treasurer")]
    # Seeded under the names the source records carry. They used to differ — every person
    # was "Test Person" against a "Seed Mayor" sighting — which made the fixture a
    # *renaming* scrape rather than a re-confirming one. Invisible while the review checks
    # only read the set of people; `_check_changed_fields` reads values.
    people = [await _seed_person(f"Seed {label}") for _, label in seats]
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind, "
            "                        created_at, updated_at) "
            "VALUES (%s, %s, 'scrape', %s, %s)",
            (changeset_id := str(uuid.uuid4()), _OCDID, _T1, _T1),
        )
        for person_id, (role_id, role_label) in zip(people, seats):
            post_id = await posts.find_or_create(cur, _OCDID, org, role_id, _BASE)
            await factories.bind_membership(
                cur, DerivedMembership(person_id=person_id), post_id, org, _T0
            )
            # The sighting, resolved to the seated person. Publishing renders its roster from
            # these, so without them `proposed_roster` is empty and the publish refuses.
            await cur.execute(
                "INSERT INTO source_records "
                "  (changeset_id, jurisdiction_ocdid, name, label, source_url, organization_id) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (changeset_id, _OCDID, f"Seed {role_label}", role_label, _ROSTER_URL, org),
            )
            await cur.execute(
                "INSERT INTO source_record_identities (source_record_id, person_id) "
                "VALUES (%s, %s)",
                ((await cur.fetchone())[0], person_id),
            )
        await conn.commit()

    # The same people in the same seats, so the reviewer's card would raise nothing.
    await _apply_scrape_changes(changeset_id, _OCDID)

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT published_at IS NOT NULL, dismissed_at IS NOT NULL "
            "FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        published, dismissed = await cur.fetchone()
        await cur.execute(
            "SELECT min(last_seen_at) FROM memberships WHERE person_id = ANY(%s)",
            (people,),
        )
        last_seen_at = (await cur.fetchone())[0]

    assert published, "a re-confirmed roster should publish, not sit unresolved"
    assert not dismissed, "it should no longer be dismissed as unchanged"
    assert last_seen_at > _T0, "publishing is what advances last_seen_at"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_scrape_the_pipeline_reported_an_issue_on_does_not_publish():
    """The same re-confirmed roster as above, plus one pending issue — so the only difference
    between publishing and not is the issue.

    `review_summary_for_changeset` derives its issues from the two rosters and never reads the
    `issues` table, so a `cost_cap_reached` run — one that stopped at its ceiling before it had
    the roster it was looking for — published its partial roster as "nothing to review". The
    issues were also filed *after* the publish decision, so they could not have gated it even
    if it had asked.
    """
    from core.post_derivation import DerivedMembership
    from database.issues import upsert_issue
    from services.people_collector import _apply_scrape_changes
    from shared.utils.statuses import PipelineIssueType

    seats = [("mayor", "Mayor"), ("clerk", "Clerk"), ("treasurer", "Treasurer")]
    people = [await _seed_person(f"Seed {label}") for _, label in seats]
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind, "
            "                        created_at, updated_at) "
            "VALUES (%s, %s, 'scrape', %s, %s)",
            (changeset_id := str(uuid.uuid4()), _OCDID, _T1, _T1),
        )
        for person_id, (role_id, role_label) in zip(people, seats):
            post_id = await posts.find_or_create(cur, _OCDID, org, role_id, _BASE)
            await factories.bind_membership(
                cur, DerivedMembership(person_id=person_id), post_id, org, _T0
            )
            await cur.execute(
                "INSERT INTO source_records "
                "  (changeset_id, jurisdiction_ocdid, name, label, source_url, organization_id) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (changeset_id, _OCDID, f"Seed {role_label}", role_label, _ROSTER_URL, org),
            )
            await cur.execute(
                "INSERT INTO source_record_identities (source_record_id, person_id) "
                "VALUES (%s, %s)",
                ((await cur.fetchone())[0], person_id),
            )
        await conn.commit()

    # The issue hangs off the run, and `has_pending_issues` reaches it through the changeset
    # that run produced — so the fixture needs a real run, which the foreign key now insists on.
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO pipeline_runs (id, jurisdiction_ocdid, arguments_json, status, "
            "  changeset_id, finished_at) "
            "VALUES (gen_random_uuid(), %s, '{}'::jsonb, 'SUCCESS', %s, now()) RETURNING id::text",
            (_OCDID, changeset_id),
        )
        run_id = (await cur.fetchone())[0]
        await conn.commit()

    await upsert_issue(
        run_id, PipelineIssueType.COST_CAP_REACHED, [{"spent_usd": "0.5000"}]
    )

    await _apply_scrape_changes(changeset_id, _OCDID)

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT published_at IS NOT NULL FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        published = (await cur.fetchone())[0]

    assert not published, "a scrape with a pending issue published itself unreviewed"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_partial_term_date_is_stored_as_the_source_gave_it():
    """Sources give "2024" and "2024-05" far more often than a full date — 3,513 of 4,547 on
    dev. `date` cannot hold either, so the column is text, like `people`'s and for the same
    reason Popolo allows them."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        membership_id = await factories.bind_membership(
            cur,
            DerivedMembership(person_id=person_id, start_date="2024", end_date="2028-01"),
            post_id,
            org,
            _T0,
        )

        await cur.execute(
            "SELECT start_date, end_date FROM memberships WHERE id::text = %s",
            (membership_id,),
        )
        assert await cur.fetchone() == ("2024", "2028-01")
        await conn.rollback()


# --- a reviewer's pick ------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_pick_is_keyed_on_the_person_not_the_post():
    """`chosen_posts` used to key on `post_id`, which meant the pick had to ride on the record
    the derivation reads. Keyed on the person, the derivation's input can be purely what the
    source said."""
    from core.post_derivation import RosterEntry
    from services.publish import chosen_posts, picks_in

    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await conn.commit()

    roster = [
        RosterEntry(
            id="p1",
            jurisdiction_ocdid=_OCDID,
            post_id=post_id,
        )
    ]

    assert await chosen_posts(picks_in(roster)) == {
        "p1": ChosenPost(organization_id=org, role_id="mayor", division_ocdid=_BASE)
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_pick_at_a_post_that_is_gone_is_simply_absent():
    """Not an error and not a lost person: the derivation falls back to the label."""
    from core.post_derivation import RosterEntry
    from services.publish import chosen_posts, picks_in

    roster = [
        RosterEntry(
            id="p1",
            jurisdiction_ocdid=_OCDID,
            post_id="00000000-0000-4000-8000-00000000dead",
        )
    ]

    assert await chosen_posts(picks_in(roster)) == {}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_persons_term_is_read_off_the_seat_they_hold():
    """`people` has no term columns since 145 — a term belongs to the tenure. The person read
    still answers, by projecting the open membership, as it already does for `office`."""
    from database.people import get_roster

    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await factories.bind_membership(
            cur,
            DerivedMembership(person_id=person_id, start_date="2024", end_date="2028-01"),
            post_id,
            org,
            _T0,
        )
        await conn.commit()

    roster = await get_roster(jurisdiction_ocdid=_OCDID)
    seated = next(p for p in roster if p["id"] == person_id)
    assert (seated["start_date"], seated["end_date"]) == ("2024", "2028-01")


# --- per organization ------------------------------------------------------------------------


async def _published_changeset(at: datetime.datetime | None = None) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            # `updated_at` orders the reads: two scrapes of one page cannot share a date.
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind, updated_at) "
            "VALUES (%s, %s, 'scrape', coalesce(%s, clock_timestamp()))",
            (changeset_id := str(uuid.uuid4()), _OCDID, at),
        )
        await conn.commit()
    return changeset_id



async def _open_memberships(person_id: str) -> list[tuple[str, str, str]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT m.organization_id::text, p.role_id, p.division_ocdid
            FROM memberships m JOIN posts p ON p.id = m.post_id
            WHERE m.person_id = %s AND m.closed_at IS NULL
            ORDER BY p.role_id
            """,
            (person_id,),
        )
        return [tuple(row) for row in await cur.fetchall()]


async def _two_bodies() -> tuple[str, str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        council = await organizations.find_or_create(cur, _OCDID)
        mayors_office = await organizations.find_or_create(cur, _OCDID, "Office of the Mayor")
        await conn.commit()
    return council, mayors_office


async def _publish(*sightings: tuple[str, str, str], at: datetime.datetime = _T0) -> str:
    """A published scrape that read these `(organization, person, label)` sightings.

    Publish takes no roster: the records are the input, so a test says what the page said and
    publishing is what lets the fold see it.
    """
    changeset_id = await _published_changeset(at)
    for organization_id, person_id, label in sightings:
        await _record_for(changeset_id, organization_id, person_id, label)
    await _date_records(changeset_id, at)
    from database.publications import publish_changeset

    await publish_changeset(changeset_id, _OCDID)
    return changeset_id


async def _date_records(changeset_id: str, at: datetime.datetime) -> None:
    """The insert stamps `now()`; a scrape's records carry its date, which the fold reads as
    when the membership was first and last seen."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE source_records SET created_at = %s WHERE changeset_id = %s",
            (at, changeset_id),
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_person_in_two_organizations_holds_an_open_membership_in_each():
    person_id = await _seed_person("Ana Reyes")
    council, mayors_office = await _two_bodies()

    await _publish(
        (council, person_id, "Council Member Ward 3"),
        (mayors_office, person_id, "Mayor"),
    )

    assert await _open_memberships(person_id) == [
        (council, "council-member", _WARD_3),
        (mayors_office, "mayor", _BASE),
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_move_in_one_organization_leaves_the_others_membership_open():
    person_id = await _seed_person("Ana Reyes")
    council, mayors_office = await _two_bodies()
    await _publish(
        (council, person_id, "Council Member Ward 3"),
        (mayors_office, person_id, "Mayor"),
    )

    # The council page moves her to the at-large seat; the mayor's office page is unchanged.
    await _publish(
        (council, person_id, "Council Member"),
        (mayors_office, person_id, "Mayor"),
        at=_T1,
    )

    assert await _open_memberships(person_id) == [
        (council, "council-member", _BASE),
        (mayors_office, "mayor", _BASE),
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reviewing_a_roster_restating_two_bodies_proposes_no_move():
    """This read `proposals_for_requests`, which compared a hand-built roster against the
    memberships we held. It now reads the fold's own two sides, because that is what the card
    and the import report compare and a second answer could disagree with them."""
    person_id = await _seed_person("Ana Reyes")
    council, mayors_office = await _two_bodies()
    await _publish(
        (council, person_id, "Council Member Ward 3"),
        (mayors_office, person_id, "Mayor"),
    )
    changeset_id = await _restating(
        (council, person_id, "Council Member Ward 3"),
        (mayors_office, person_id, "Mayor"),
    )

    existing, proposed, _overridden = await card_sides(changeset_id, _OCDID)

    [change] = changes_of(existing, proposed)
    assert change.offices == []
    assert change.kind is ChangeKind.UNCHANGED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_proposal_names_a_post_by_the_name_a_human_gave_it():
    """Both ends: the post a scrape restates, and the post someone would leave.

    Moved onto the fold with the test above. It is also what caught the fold rendering a
    derived name over a curator's: naming a post is a claim on the POST entity, which
    `database/facts.py` does not load, so `display_rows` takes the names as an overlay.
    """
    staying = await _seed_person("Ana Reyes")
    leaving = await _seed_person("Bo Chen")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        council = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, council, "council-member", _BASE)
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'email', %s, %s, 'admins') RETURNING id::text",
            (_CURATOR, _CURATOR, _CURATOR.replace("@", "-")),
        )
        curator_id = (await cur.fetchone())[0]
        await posts.set_post_label(cur, post_id, "Position 8", curator_id)
        for person_id in (staying, leaving):
            await factories.bind_membership(cur, DerivedMembership(person_id=person_id), post_id, council, _T0)
        await conn.commit()
    await _publish(
        (council, staying, "Council Member"), (council, leaving, "Council Member")
    )
    changeset_id = await _restating((council, staying, "Council Member"))

    existing, proposed, _overridden = await card_sides(changeset_id, _OCDID)

    changes = {change.person_id: change for change in changes_of(existing, proposed)}
    assert changes[staying].kind is ChangeKind.UNCHANGED
    assert changes[leaving].kind is ChangeKind.ABSENT
    assert [office.post_label for office in changes[leaving].offices] == ["Position 8"]
    assert _post_label_of(existing, staying) == "Position 8"


async def _restating(*sightings: tuple[str, str, str]) -> str:
    """An unpublished scrape that read these `(organization, person, label)` sightings — what a
    reviewer is looking at when they open its card."""
    changeset_id = await _published_changeset()
    for organization_id, person_id, label in sightings:
        await _record_for(changeset_id, organization_id, person_id, label)
    return changeset_id


def _post_label_of(rows: list[dict], person_id: str) -> str:
    [row] = [row for row in rows if row["id"] == person_id]
    return row["memberships"][0]["post_label"]


async def _record_for(changeset_id: str, organization_id: str, person_id: str, label: str) -> None:
    """What makes an organization enumerated: this changeset read a page for it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name FROM people WHERE id = %s", (person_id,))
        name = (await cur.fetchone())[0]
    await insert_source_records(
        changeset_id,
        _OCDID,
        {
            person_id: [
                {
                    "name": name,
                    "label": label,
                    "source_url": _ROSTER_URL,
                    "organization_id": organization_id,
                }
            ]
        },
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_body_the_scrape_never_read_keeps_its_people():
    """The rule step 9 turns on: a run that read one body cannot retire anyone in another.

    The scrape reads the mayor's office only, and names somebody else there. Ana loses the
    mayor's office, where the page no longer lists her, and keeps the council, which nothing
    read.
    """
    person_id = await _seed_person("Ana Reyes")
    other_id = await _seed_person("Bo Chen")
    council, mayors_office = await _two_bodies()
    await _publish(
        (council, person_id, "Council Member Ward 3"),
        (mayors_office, person_id, "Mayor"),
    )

    await _publish((mayors_office, other_id, "Mayor"), at=_T1)

    assert await _open_memberships(person_id) == [(council, "council-member", _WARD_3)]
    assert await _open_memberships(other_id) == [(mayors_office, "mayor", _BASE)]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_body_whose_extraction_returned_nobody_closes_nobody():
    """An empty result is a failed scrape more often than a dissolved body, and a changeset
    with no record for the council never says the council was read."""
    person_id = await _seed_person("Ana Reyes")
    council, _ = await _two_bodies()
    await _publish((council, person_id, "Council Member Ward 3"))

    await _publish(at=_T1)

    assert await _open_memberships(person_id) == [(council, "council-member", _WARD_3)]


async def _curator_id(cur) -> str:
    """`claims.created_by` is a foreign key, so a claim needs somebody to have made it."""
    await cur.execute("SELECT id::text FROM users WHERE email = %s", (_CURATOR,))
    row = await cur.fetchone()
    if row:
        return row[0]
    await cur.execute(
        "INSERT INTO users (email, provider, provider_user_id, username, role) "
        "VALUES (%s, 'email', %s, %s, 'admins') RETURNING id::text",
        (_CURATOR, _CURATOR, _CURATOR.replace("@", "-")),
    )
    return (await cur.fetchone())[0]



async def _held_post_id(person_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT post_id::text FROM memberships "
            "WHERE person_id = %s AND closed_at IS NULL",
            (person_id,),
        )
        return (await cur.fetchone())[0]


def _posts_claim(person_id: str, post_id: str, kind: ClaimKind) -> Claim:
    return Claim(
        entity_type=EntityType.PERSON,
        entity_id=person_id,
        field_path=POSTS_FIELD,
        kind=kind,
        value=post_id,
        sources=[Source(note=DefaultNote.EDITED)],
    )


async def _reject_post(person_id: str) -> str:
    """Somebody says this person does not hold the post, and which post they said it about.

    The claim is about the person: the rebuild deletes and remints the membership row, so the
    row id is no use for taking the claim back, but `(person, post)` outlives it.
    """
    post_id = await _held_post_id(person_id)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await claims.upsert(
            cur,
            _posts_claim(person_id, post_id, ClaimKind.REJECT),
            await _curator_id(cur),
        )
        await conn.commit()
    return post_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_membership_somebody_said_never_held_closes_at_publish():
    """The reviewer's act is a claim, and publishing is what applies it — so a review that is
    never approved leaves the published roster alone."""
    person_id = await _seed_person("Ana Reyes")
    council, _ = await _two_bodies()
    await _publish((council, person_id, "Council Member Ward 3"))

    await _reject_post(person_id)
    assert await _open_memberships(person_id) == [(council, "council-member", _WARD_3)]

    await _publish(at=_T1)

    assert await _open_memberships(person_id) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_withdrawing_the_claim_reopens_the_membership_on_the_next_publish():
    """What rollback does: withdraw the claim, publish again, and the derivation puts them back.
    Nothing here knows about undo — the state is the derivation of evidence and live claims."""
    person_id = await _seed_person("Ana Reyes")
    council, _ = await _two_bodies()
    await _publish((council, person_id, "Council Member Ward 3"))
    post_id = await _reject_post(person_id)
    await _publish(at=_T1)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await claims.withdraw(
            cur,
            EntityType.PERSON,
            person_id,
            POSTS_FIELD,
            ClaimKind.REJECT,
            await _curator_id(cur),
            value=post_id,
        )
        await conn.commit()

    await _publish(at=_T2)

    assert await _open_memberships(person_id) == [(council, "council-member", _WARD_3)]
