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
            "UPDATE posts SET label = %s, headcount = %s WHERE id = %s",
            ("Councillors", 9, post_id),
        )
        await posts.find_or_create(cur, _OCDID, org, "council-member", _BASE, headcount=1)

        await cur.execute(
            "SELECT label, headcount FROM posts WHERE id = %s", (post_id,)
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

        first = await memberships.record(cur, person_id, post_id, org, _T0)
        second = await memberships.record(cur, person_id, post_id, org, _T1)
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

        old = await memberships.record(cur, person_id, mayor, org, _T0)
        new = await memberships.record(cur, person_id, ward, org, _T1)
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
        await memberships.record(cur, person_id, post_id, org, _T0)

        assert await memberships.close_absent(cur, _OCDID, [], _T1) == 0
        assert await memberships.close_absent(cur, _OCDID, [str(uuid.uuid4())], _T1) == 1
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_last_seen_at_is_derived_from_memberships():
    """The column was dropped from `posts`: a post is produced exactly when somebody parses
    into it, so the answer is MAX over its memberships."""
    person_id = await _seed_person()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        await memberships.record(cur, person_id, post_id, org, _T1)

        rows = await posts.list_for_jurisdiction(cur, _OCDID)
        assert {row["id"]: row["last_seen_at"] for row in rows}[post_id] == _T1

        assert await posts.unseen_since(cur, _OCDID, _T0) == []
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

        await memberships.record(
            cur, first_person, bucket, org, _T0, unmatched_text=["Town Moderator"]
        )
        await memberships.record(
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
