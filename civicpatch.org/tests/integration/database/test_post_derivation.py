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

from database import divisions, memberships, organizations, posts
from database.database import get_pool
from database.review_queue import issue_count, issue_priority

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:testville/government"
_BASE = "ocd-division/country:us/state:zz/place:testville"
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
            "INSERT INTO people (id, jurisdiction_ocdid, data) VALUES (%s, %s, %s)",
            (person_id, _OCDID, json.dumps({"name": "Test Person"})),
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

        first = await memberships.upsert(cur, person_id, post_id, org, _T0)
        second = await memberships.upsert(cur, person_id, post_id, org, _T1)
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

        old = await memberships.upsert(cur, person_id, mayor, org, _T0)
        new = await memberships.upsert(cur, person_id, ward, org, _T1)
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
        await memberships.upsert(cur, person_id, post_id, org, _T0)

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
        await memberships.upsert(cur, person_id, post_id, org, _T0)
        await cur.execute("UPDATE posts SET _is_tracked = false WHERE id = %s", (post_id,))

        assert await memberships.close_absent(cur, _OCDID, [str(uuid.uuid4())], _T1) == 1
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_post_is_unverified_until_a_publish_puts_somebody_in_it():
    """Ingest mints the post; only publish writes the membership. The gap between them is
    exactly the window in which nobody has answered for the office a scrape invented."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        unverified = await posts.unverified_by_jurisdiction(cur, [_OCDID])
        assert [post["id"] for post in unverified[_OCDID]] == [post_id]

        await memberships.upsert(cur, person_id, post_id, org, _T0)
        assert await posts.unverified_by_jurisdiction(cur, [_OCDID]) == {_OCDID: []}
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unverified_post_raises_the_queue_score_and_the_badge():
    """The card shows stored issues plus unverified posts, so the queue must count both — a
    badge reading `0 issues` over a card that opens with one is the discrepancy this closes.

    Evaluated against a literal roster rather than an inserted request: the review pool is
    shared, and a spare request for this jurisdiction would reach unrelated tests.
    """
    await _seed_person()  # for the jurisdiction row the organization FK needs
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        await cur.execute(
            f"SELECT {issue_count('t.j', 't.ocdid')}, {issue_priority('t.j', 't.ocdid')} "
            "FROM (VALUES (NULL::jsonb, %s)) t(j, ocdid)",
            (_OCDID,),
        )
        count, priority = await cur.fetchone()
        assert count == 1, "a scrape with no stored issues still has an unanswered post"
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
            "INSERT INTO people (id, jurisdiction_ocdid, data) VALUES (%s, %s, %s)",
            (second := str(uuid.uuid4()), _OCDID, json.dumps({"name": "Other"})),
        )
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)

        bucket = await posts.find_or_create(cur, _OCDID, org, "unmatched", _BASE)
        again = await posts.find_or_create(cur, _OCDID, org, "unmatched", _BASE)
        assert bucket == again

        await memberships.upsert(
            cur, first_person, bucket, org, _T0, unmatched_text=["Town Moderator"]
        )
        await memberships.upsert(
            cur, second, bucket, org, _T0, unmatched_text=["Supervisor of the Checklist"]
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
            division_ocdid=_BASE,
            headcount=1,
            members=[DerivedMember(person_id=person_id)],
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
        await cur.execute("DELETE FROM requests WHERE id = %s", (request_id,))
        await conn.commit()


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
        await memberships.upsert(cur, person_id, held, org, _T0)

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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_human_label_survives_a_re_scrape():
    """The only human-owned field on a membership. Protected by being absent from `upsert`'s
    ON CONFLICT SET — the derived parts beside it are overwritten every publish."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "council-member", _BASE)

        membership_id = await memberships.upsert(
            cur, person_id, post_id, org, _T0, designations=["Position 8"]
        )
        assert await memberships.update_label(cur, membership_id, "Councilmember Pos. 8") is True

        # A later scrape of the same seat, with the designation parsed differently.
        await memberships.upsert(
            cur, person_id, post_id, org, _T1, designations=["Position 08"]
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

        old = await memberships.upsert(cur, person_id, first, org, _T0)
        await memberships.update_label(cur, old, "Councilmember Pos. 8")
        new = await memberships.upsert(cur, person_id, second, org, _T1)

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
        await memberships.upsert(cur, person_id, post_id, org, _T0)

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
            cur, person_id, post_id, org, _T0, role_ids=["treasurer", "assessor"]
        )
        await cur.execute(
            "SELECT role_id FROM membership_roles WHERE membership_id::text = %s "
            "ORDER BY role_id",
            (membership_id,),
        )
        assert [r[0] for r in await cur.fetchall()] == ["assessor", "treasurer"]

        # Derived from the label, so the newest scrape's answer is the whole answer — a role
        # the page stopped naming must not linger.
        await memberships.upsert(cur, person_id, post_id, org, _T0, role_ids=["treasurer"])
        await cur.execute(
            "SELECT role_id FROM membership_roles WHERE membership_id::text = %s",
            (membership_id,),
        )
        assert [r[0] for r in await cur.fetchall()] == ["treasurer"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_scrape_seeds_the_membership_label_but_never_overwrites_one():
    """`label` is in the INSERT and not the DO UPDATE SET. That omission is the only thing
    protecting a curator's edit, and no unit test can see it — it takes two real upserts."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)

        first = await memberships.upsert(
            cur, person_id, post_id, org, _T0, label="Commissioner Of Public Safety"
        )
        await cur.execute("SELECT label FROM memberships WHERE id = %s", (first,))
        assert (await cur.fetchone())[0] == "Commissioner Of Public Safety"

        await memberships.update_label(cur, first, "Public Safety Commissioner")

        # The next scrape derives the same proposal and must lose to the human.
        again = await memberships.upsert(
            cur, person_id, post_id, org, _T1, label="Commissioner Of Public Safety"
        )
        assert again == first

        await cur.execute(
            "SELECT label, last_seen_at FROM memberships WHERE id = %s", (first,)
        )
        label, last_seen_at = await cur.fetchone()
        assert label == "Public Safety Commissioner"
        # The rest of the row still advances — protection is per-column, not a skipped write.
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
            cur, person_id, post_id, org, _T0, label="Mayor, At-Large"
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
        membership_id = await memberships.upsert(cur, person_id, post_id, org, _T1)

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
        membership_id = await memberships.upsert(cur, person_id, post_id, org, _T0)
        await cur.execute(
            "UPDATE memberships SET closed_at = %s WHERE id = %s", (_T0, membership_id)
        )

        assert await memberships.advance_last_seen_at(cur, [person_id], _T1) == 0
        await conn.rollback()
