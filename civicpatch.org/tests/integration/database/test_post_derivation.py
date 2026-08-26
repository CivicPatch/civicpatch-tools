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

from core.post_derivation import DerivedMember
from database import divisions, memberships, organizations, posts
from database.database import get_pool
from database.review_queue import issue_count, issue_priority

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:testville/government"
_BASE = "ocd-division/country:us/state:zz/place:testville"
_CURATOR = "zz-post-derivation-curator@example.com"
_WARD_3 = f"{_BASE}/ward:3"

_T0 = datetime.datetime(2026, 3, 11, tzinfo=datetime.timezone.utc)
_T1 = datetime.datetime(2026, 6, 2, tzinfo=datetime.timezone.utc)


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
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
        # Before the jurisdictions themselves: `requests.jurisdiction_ocdid` is a FK, and
        # test_publish_writes_memberships_for_the_roster leaves a request behind. Without
        # this the wipe raises at *setup* of every test in the file, so one leftover row
        # takes the whole module down — and takes new breakage with it, silently.
        # `source_records` and `pipeline_runs` cascade from the request.
        await cur.execute("DELETE FROM requests WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        # The curator, and the assertions pointing at them. `asserted_by` is a FK, so the user
        # cannot go first — and `assertions` has none to memberships, so its rows outlive the
        # memberships they describe and would otherwise accumulate across runs.
        await cur.execute(
            "DELETE FROM assertions WHERE asserted_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_CURATOR,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_CURATOR,))
        # Otherwise `add_post` rows survive the run and the mint counts below climb.
        await cur.execute(
            "DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed_person():
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
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) "
            "VALUES (%s, %s, %s)",
            (person_id, _OCDID, "Test Person"),
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
    """The reason `DO NOTHING` is not `DO UPDATE`: label and headcount are human-owned, and
    the derivation has no update path to reach them."""
    await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "council-member", _BASE, headcount=1)

        await cur.execute(
            "UPDATE posts SET label = %s, _headcount = %s WHERE id = %s",
            ("Councillors", 9, post_id),
        )
        await posts.find_or_create(cur, _OCDID, org, "council-member", _BASE, headcount=1)

        await cur.execute(
            "SELECT label, _headcount FROM posts WHERE id = %s", (post_id,)
        )
        assert await cur.fetchone() == ("Councillors", 9)
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

        first = await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T0)
        second = await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T1)
        assert first == second

        await cur.execute(
            "SELECT first_seen_at, last_seen_at FROM memberships WHERE id = %s", (first,)
        )
        assert await cur.fetchone() == (_T0, _T1)
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_different_post_closes_the_old_membership_and_opens_a_new_one():
    """Closing rather than moving is what leaves history for the roster timeline."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await divisions.find_or_create(cur, _WARD_3, _OCDID)
        mayor = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        ward = await posts.find_or_create(cur, _OCDID, org, "council-member", _WARD_3)

        old = await memberships.upsert(cur, DerivedMember(person_id=person_id), mayor, org, _T0)
        new = await memberships.upsert(cur, DerivedMember(person_id=person_id), ward, org, _T1)
        assert old != new

        await cur.execute("SELECT closed_at FROM memberships WHERE id = %s", (old,))
        assert (await cur.fetchone())[0] == _T1
        await cur.execute(
            "SELECT count(*) FROM memberships WHERE person_id = %s AND closed_at IS NULL",
            (person_id,),
        )
        assert (await cur.fetchone())[0] == 1
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_close_absent_ignores_an_empty_roster():
    """An empty roster is a failed scrape, not a dissolved council — the same guard
    `publish_request` already applies before retiring people."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T0)

        assert await memberships.close_absent(cur, _OCDID, [], _T1) == 0
        assert await memberships.close_absent(cur, _OCDID, [str(uuid.uuid4())], _T1) == 1
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_close_absent_closes_an_untracked_posts_membership_too():
    """`closed_at` is transaction time — it records that we stopped seeing someone, not that
    they left, so it is true of an untracked post as much as a tracked one. `_is_tracked`
    gates whether anyone is asked to look, which is the review queue, not the record."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T0)
        await cur.execute("UPDATE posts SET _is_tracked = false WHERE id = %s", (post_id,))

        assert await memberships.close_absent(cur, _OCDID, [str(uuid.uuid4())], _T1) == 1
        await conn.rollback()


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

        await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T0)
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

        await memberships.upsert(
            cur, DerivedMember(person_id=first_person, unmatched_text=["Town Moderator"]), bucket, org, _T0
        )
        await memberships.upsert(
            cur, DerivedMember(person_id=second, unmatched_text=["Supervisor of the Checklist"]), bucket, org, _T0
        )

        await cur.execute(
            "SELECT unmatched_text FROM memberships WHERE post_id = %s ORDER BY unmatched_text",
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
    """The publish half end to end: posts re-ensured, memberships opened, absentees closed.

    Posts are re-ensured here because ingest is never fatal — a roster must publish even if
    post derivation failed at submit.
    """
    from core.post_derivation import DerivedMember, DerivedPost
    from database.publications import publish_request

    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO requests (id, jurisdiction_ocdid, request_type)
            VALUES (%s, %s, 'pipeline_run')
            ON CONFLICT (id) DO NOTHING
            """,
            (request_id := str(uuid.uuid4()), _OCDID),
        )
        # Every registration path creates one, and publish reads its `updated_at` as the
        # observation's clock — so this is where `_T0` has to go.
        await cur.execute(
            """
            INSERT INTO pipeline_runs (request_id, status, progress, created_at, updated_at)
            VALUES (%s, 'SUCCESS', 100, %s, %s)
            ON CONFLICT (request_id) DO NOTHING
            """,
            (request_id, _T0, _T0),
        )
        await conn.commit()

    people = [
        {
            "id": person_id,
            "name": "Robert Michaud",
            "office": {"name": "Mayor"},
            "jurisdiction_ocdid": _OCDID,
            "source_urls": ["https://example.gov"],
            "updated_at": "2026-03-11T00:00:00+00:00",
        }
    ]
    derived = [
        DerivedPost(
            role_id="mayor",
            role_label="Mayor",
            division_ocdid=_BASE,
            headcount=1,
            members=[DerivedMember(person_id=person_id, source_labels=["Mayor"])],
        )
    ]

    written = await publish_request(request_id, _OCDID, people, None, derived=derived)
    assert written == 1

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT p.role_id, m.first_seen_at, m.closed_at
            FROM memberships m JOIN posts p ON p.id = m.post_id
            WHERE p.jurisdiction_ocdid = %s
            """,
            (_OCDID,),
        )
        rows = await cur.fetchall()
        assert len(rows) == 1
        role_id, first_seen_at, closed_at = rows[0]
        assert role_id == "mayor"
        assert closed_at is None
        # The Record's own updated_at, not the moment publish ran.
        assert first_seen_at == _T0

        # Asserted on the stored row rather than on the dict the row builder produced: since
        # 136 these columns are the record, so a publish that shapes them wrong has nowhere
        # else to be right.
        await cur.execute(
            "SELECT name, source_urls, emails FROM people WHERE id = %s",
            (person_id,),
        )
        name, source_urls, emails = await cur.fetchone()
        assert name == "Robert Michaud"
        assert source_urls == ["https://example.gov"]
        assert emails == [], "a person with no emails has none, not NULL"

        await cur.execute("DELETE FROM requests WHERE id = %s", (request_id,))
        await conn.commit()

    # `office` is no longer stored — it is rebuilt from the membership publish just wrote.
    # Asserted through the reader the jurisdiction modal actually calls, because the failure
    # mode is not an exception: it is a subtitle that silently goes blank.
    from database.people import get_person_models

    roster = await get_person_models(_OCDID)
    assert len(roster) == 1
    office = roster[0].model_extra["office"]
    assert office["name"] == "Mayor"
    assert office["division_ocdid"] == _BASE

    # `memberships` is what replaces `office`: plural, because the schema allows a person one
    # open membership *per organization* and a jurisdiction can have several bodies. Carried
    # inline so a consumer needs one read, not a join against a second endpoint.
    memberships_inline = roster[0].model_extra["memberships"]
    assert len(memberships_inline) == 1
    held = memberships_inline[0]
    assert held["role_id"] == "mayor"
    assert held["division_ocdid"] == _BASE
    # The source's own words, which is what `office.name` always was.
    assert held["source_labels"] == ["Mayor"]


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
        await cur.execute("SELECT _headcount FROM posts WHERE id::text = %s", (created,))
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
        await memberships.upsert(cur, DerivedMember(person_id=person_id), held, org, _T0)

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

        assert await posts.update_human_fields(cur, post_id, "Trustees", 5, True) is True
        await cur.execute(
            "SELECT label, _headcount FROM posts WHERE id::text = %s", (post_id,)
        )
        assert await cur.fetchone() == ("Trustees", 5)

        assert (
            await posts.update_human_fields(
                cur, "00000000-0000-0000-0000-000000000000", None, 1, True
            )
            is False
        )
        await conn.rollback()


async def _human_sets_label(cur, membership_id: str, label: str) -> None:
    """What `assign` does. `set_label` with a user is the whole human edit: the value and the
    assertion saying somebody chose it, which is what survives the next scrape."""
    # `assertions.asserted_by` is a foreign key, so an assertion needs somebody to have made it.
    await cur.execute(
        "INSERT INTO users (email, provider, provider_user_id, role) "
        "VALUES (%s, 'email', %s, 'admins') RETURNING id::text",
        (_CURATOR, _CURATOR),
    )
    curator_id = (await cur.fetchone())[0]

    await memberships.set_label(cur, membership_id, label, curator_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_asserted_label_survives_a_re_scrape():
    """The only human-owned field on a membership, and only once a human has claimed it."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "council-member", _BASE)

        membership_id = await memberships.upsert(
            cur, DerivedMember(person_id=person_id, designations=["Position 8"]), post_id, org, _T0
        )
        await _human_sets_label(cur, membership_id, "Councilmember Pos. 8")

        # A later scrape of the same seat, with the designation parsed differently.
        await memberships.upsert(
            cur, DerivedMember(person_id=person_id, designations=["Position 08"]), post_id, org, _T1
        )

        await cur.execute(
            "SELECT label, designations FROM memberships WHERE id::text = %s",
            (membership_id,),
        )
        label, designations = await cur.fetchone()
        assert label == "Councilmember Pos. 8"  # untouched
        assert designations == ["Position 08"]  # re-derived


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moving_to_another_post_leaves_the_label_behind():
    """A label names this person in *this* seat, so a different seat starts unnamed."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await divisions.find_or_create(cur, _WARD_3, _OCDID)
        first = await posts.find_or_create(cur, _OCDID, org, "council-member", _BASE)
        second = await posts.find_or_create(cur, _OCDID, org, "council-member", _WARD_3)

        old = await memberships.upsert(cur, DerivedMember(person_id=person_id), first, org, _T0)
        await memberships.set_label(cur, old, "Councilmember Pos. 8")
        new = await memberships.upsert(cur, DerivedMember(person_id=person_id), second, org, _T1)

        await cur.execute(
            "SELECT label FROM memberships WHERE id::text = ANY(%s) ORDER BY first_seen_at",
            ([old, new],),
        )
        assert [row[0] for row in await cur.fetchall()] == ["Councilmember Pos. 8", None]


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
        await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T0)

        rows = await memberships.list_for_jurisdiction(cur, _OCDID)
        assert len(rows) == 1
        assert rows[0]["role_id"] == "mayor"
        assert rows[0]["label"] is None
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_label_naming_two_offices_keeps_the_loser_on_the_membership():
    """One open membership per person per body means one role must define the post. Without
    somewhere for the other to land it was simply dropped — a clerk who is also treasurer
    published as a clerk, and the treasurership vanished."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "clerk", _BASE)
        membership_id = await memberships.upsert(
            cur, DerivedMember(person_id=person_id, role_ids=["treasurer", "assessor"]), post_id, org, _T0
        )
        await cur.execute(
            "SELECT role_id FROM membership_roles WHERE membership_id::text = %s "
            "ORDER BY role_id",
            (membership_id,),
        )
        assert [r[0] for r in await cur.fetchall()] == ["assessor", "treasurer"]

        # Derived from the label, so the newest scrape's answer is the whole answer — a role
        # the page stopped naming must not linger.
        await memberships.upsert(cur, DerivedMember(person_id=person_id, role_ids=["treasurer"]), post_id, org, _T0)
        await cur.execute(
            "SELECT role_id FROM membership_roles WHERE membership_id::text = %s",
            (membership_id,),
        )
        assert [r[0] for r in await cur.fetchall()] == ["treasurer"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_scrape_reworded_by_nobody_is_re_derived():
    """The other half of the rule, and the reason the guard is conditional.

    `label` used to be absent from the DO UPDATE SET entirely, which protected a curator's
    edit and also froze every label nobody had touched — so no parser improvement could ever
    reach a membership that already existed. Takes two real upserts to see."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        first = await memberships.upsert(
            cur, DerivedMember(person_id=person_id, label="Commissioner Of Public Safety"), post_id, org, _T0
        )
        await cur.execute("SELECT label FROM memberships WHERE id = %s", (first,))
        assert (await cur.fetchone())[0] == "Commissioner Of Public Safety"

        # A later scrape whose parser words it better. Nobody has asserted anything, so the
        # improvement lands.
        again = await memberships.upsert(
            cur, DerivedMember(person_id=person_id, label="Public Safety Commissioner"), post_id, org, _T1
        )
        assert again == first

        await cur.execute(
            "SELECT label, last_seen_at FROM memberships WHERE id = %s", (first,)
        )
        label, last_seen_at = await cur.fetchone()
        assert label == "Public Safety Commissioner"
        assert last_seen_at == _T1
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_advancing_last_seen_leaves_everything_else_alone():
    """Transaction time only. `close_absent` is the direction that needs review; still being
    on the same page is not a change and should not wait for a human."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        membership_id = await memberships.upsert(
            cur, DerivedMember(person_id=person_id, label="Mayor, At-Large"), post_id, org, _T0
        )

        assert await memberships.advance_last_seen_at(cur, [person_id], _T1) == 1

        await cur.execute(
            "SELECT first_seen_at, last_seen_at, closed_at, label FROM memberships WHERE id = %s",
            (membership_id,),
        )
        first_seen_at, last_seen_at, closed_at, label = await cur.fetchone()
        assert last_seen_at == _T1
        # Nothing else moves: not the interval's start, not the human-owned label.
        assert first_seen_at == _T0
        assert closed_at is None
        assert label == "Mayor, At-Large"
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_last_seen_never_walks_backwards():
    """Scrapes can land out of order. GREATEST is what stops a late arrival from a stale run
    making a roster look older than it is."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        membership_id = await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T1)

        await memberships.advance_last_seen_at(cur, [person_id], _T0)

        await cur.execute("SELECT last_seen_at FROM memberships WHERE id = %s", (membership_id,))
        assert (await cur.fetchone())[0] == _T1
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_closed_membership_is_not_reopened_by_being_seen():
    """Someone who left is not brought back by a scrape naming them. Reopening is a decision,
    and this is only a clock."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        membership_id = await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T0)
        await cur.execute(
            "UPDATE memberships SET closed_at = %s WHERE id = %s", (_T0, membership_id)
        )

        assert await memberships.advance_last_seen_at(cur, [person_id], _T1) == 0
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
        await memberships.upsert(cur, DerivedMember(person_id=person_id), other, org, _T0)
        await conn.commit()


async def _seed_request() -> str:
    request_id = str(uuid.uuid4())
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
        await cur.execute(
            "INSERT INTO requests (id, jurisdiction_ocdid, request_type) "
            "VALUES (%s, %s, 'pipeline_run')",
            (request_id, _OCDID),
        )
        await conn.commit()
    return request_id


async def _add_post_logs(request_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changes, user_id FROM change_logs "
            "WHERE type = 'add_post' AND request_id = %s",
            (request_id,),
        )
        return [{"changes": row[0], "user_id": row[1]} for row in await cur.fetchall()]


def _derived(role_id: str, division_ocdid: str):
    from core.post_derivation import DerivedPost

    return DerivedPost(
        role_id=role_id,
        role_label=role_id.title(),
        division_ocdid=division_ocdid,
        headcount=1,
        members=[],
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_minting_a_post_is_logged_against_the_scrape_that_caused_it():
    """"This scrape invented a seat" is the event a reviewer needs told about, and it is
    answered from the log rather than a column on `posts` — creation happens once and never
    changes, so it is an event, not a property of the row."""
    request_id = await _seed_request()

    await posts.find_or_create_all(_OCDID, [_derived("mayor", _BASE)], request_id)

    logs = await _add_post_logs(request_id)
    assert len(logs) == 1
    assert logs[0]["changes"]["role_id"] == "mayor"
    # No user: nobody asserted this. A null user beside a request is what says "a scrape did
    # it" — the distinction the old code threw away by logging nothing at all.
    assert logs[0]["user_id"] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_matching_an_existing_post_logs_nothing():
    """Only a mint is news. A second scrape seeing the same seat has invented nothing, and
    logging it would make every re-scrape look like a change."""
    first = await _seed_request()
    await posts.find_or_create_all(_OCDID, [_derived("mayor", _BASE)], first)

    second = await _seed_request()
    await posts.find_or_create_all(_OCDID, [_derived("mayor", _BASE)], second)

    assert len(await _add_post_logs(first)) == 1
    assert await _add_post_logs(second) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_only_the_new_seat_is_logged_when_a_scrape_mixes_both():
    request_id = await _seed_request()
    await posts.find_or_create_all(_OCDID, [_derived("mayor", _BASE)], request_id)

    later = await _seed_request()
    await posts.find_or_create_all(
        _OCDID,
        [_derived("mayor", _BASE), _derived("council-member", _WARD_3)],
        later,
    )

    logs = await _add_post_logs(later)
    assert [log["changes"]["role_id"] for log in logs] == ["council-member"]


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
    """The point of moving `close_absent` and `advance_last_seen_at` to publish.

    Ingest used to run both, so a scrape that fetched three of seven pages closed four
    memberships with nobody in the way. They were defended as observations — "the source
    stopped listing D" is true whether or not D left office — which holds for a good scrape
    and not for a bad one, and nothing at ingest can tell which.

    Asserted through `_apply_scrape_changes` rather than through `close_absent` directly: the
    existing tests for those two call the DB functions themselves, so they stayed green when
    ingest stopped calling them at all.
    """
    from core.post_derivation import DerivedMember, DerivedPost
    from services.people_collector import _apply_scrape_changes

    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await memberships.upsert(cur, DerivedMember(person_id=person_id), post_id, org, _T0)
        await cur.execute(
            "INSERT INTO requests (id, jurisdiction_ocdid, request_type) "
            "VALUES (%s, %s, 'pipeline_run')",
            (request_id := str(uuid.uuid4()), _OCDID),
        )
        # The run too: `_apply_scrape_changes` swallows its own errors, so without this the
        # old close-at-ingest path would raise on the missing run and this test would pass
        # against the very behaviour it exists to forbid.
        await cur.execute(
            "INSERT INTO pipeline_runs (request_id, status, progress, created_at, updated_at) "
            "VALUES (%s, 'SUCCESS', 100, %s, %s)",
            (request_id, _T1, _T1),
        )
        await conn.commit()

    # A scrape naming somebody else entirely: the seated person is absent from it.
    other_id = await _seed_person()
    await _apply_scrape_changes(
        request_id,
        _OCDID,
        [
            DerivedPost(
                role_id="clerk",
                role_label="Clerk",
                division_ocdid=_BASE,
                headcount=1,
                members=[DerivedMember(person_id=other_id, source_labels=["Clerk"])],
            )
        ],
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT closed_at, last_seen_at FROM memberships WHERE person_id = %s",
            (person_id,),
        )
        closed_at, last_seen_at = await cur.fetchone()
    assert closed_at is None, "an unreviewed scrape closed a published membership"
    assert last_seen_at == _T0, "an unreviewed scrape moved a published last_seen_at"


# --- dropping the seats a dismissed scrape invented ------------------------------


async def _mint_via(request_id: str, role_id: str) -> str:
    """Mint the way ingest does, so the `add_post` log `delete_unclaimed` reads exists."""
    await posts.find_or_create_all(_OCDID, [_derived(role_id, _BASE)], request_id)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM posts WHERE jurisdiction_ocdid = %s AND role_id = %s",
            (_OCDID, role_id),
        )
        return (await cur.fetchone())[0]


async def _dismiss(request_id: str) -> None:
    from database.publications import dismiss_request

    await dismiss_request(request_id)


async def _post_exists(post_id: str) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1 FROM posts WHERE id::text = %s", (post_id,))
        return await cur.fetchone() is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dismissing_a_scrape_drops_the_seats_it_invented():
    """Dismissed, nobody is asked about the seat again — it would sit unverified for good.
    The `Board` label was the case: 44 occurrences of nothing."""
    request_id = await _seed_request()
    post_id = await _mint_via(request_id, "mayor")

    await _dismiss(request_id)

    assert await _post_exists(post_id) is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_held_seat_survives_dismissal():
    """A membership makes the post history, closed ones included."""
    request_id = await _seed_request()
    post_id = await _mint_via(request_id, "mayor")
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await memberships.upsert(
            cur, DerivedMember(person_id=person_id), post_id, org, _T0
        )
        await conn.commit()

    await _dismiss(request_id)

    assert await _post_exists(post_id) is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_vouched_seat_survives_dismissal():
    """An assertion is a person saying the seat is real, and this runs without a person.
    Where it differs from `delete_if_unheld`, which deletes assertions instead."""
    request_id = await _seed_request()
    post_id = await _mint_via(request_id, "mayor")

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'email', %s, 'admins') RETURNING id::text",
            (_CURATOR, _CURATOR),
        )
        user_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO assertions "
            "(entity_type, entity_id, field_path, kind, value, asserted_by) "
            "VALUES ('post', %s, '_headcount', 'accept', %s, %s)",
            (post_id, json.dumps(5), user_id),
        )
        await conn.commit()

    await _dismiss(request_id)

    assert await _post_exists(post_id) is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_seat_a_later_scrape_still_sees_comes_straight_back():
    """Why this needs no "did anything else see it" check: `find_or_create` re-mints a seat
    that is still real."""
    first = await _seed_request()
    post_id = await _mint_via(first, "mayor")
    await _dismiss(first)
    assert await _post_exists(post_id) is False

    later = await _seed_request()
    remade = await _mint_via(later, "mayor")

    assert await _post_exists(remade) is True
    assert remade != post_id  # a new row, not a resurrection


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dropping_leaves_another_scrapes_seats_alone():
    """Scoped to what *this* request minted. A dismissal must not tidy up a neighbour."""
    mine = await _seed_request()
    theirs = await _seed_request()
    mine_post = await _mint_via(mine, "mayor")
    theirs_post = await _mint_via(theirs, "clerk")

    await _dismiss(mine)

    assert await _post_exists(mine_post) is False
    assert await _post_exists(theirs_post) is True


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

        membership_id = await memberships.upsert(
            cur,
            DerivedMember(person_id=person_id, start_date="2024", end_date="2028-01"),
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
