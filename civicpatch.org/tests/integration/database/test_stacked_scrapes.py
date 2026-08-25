"""Integration tests for the stacked-scrape sweep and the publish guard.

Real Postgres: every guarantee here is a SQL predicate, not Python.
Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio

from database.database import get_pool
from database.publications import publish_request
from database.requests import supersede_stacked_requests

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_stacked/government"
_OTHER = "ocd-jurisdiction/country:us/state:zz/place:zz_stacked_other/government"

_OLD = "2026-03-01T00:00:00+00:00"
_MID = "2026-05-01T00:00:00+00:00"
_NEW = "2026-07-01T00:00:00+00:00"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            DELETE FROM review_session_entries
            WHERE jurisdiction_ocdid IN (%s, %s)
            """,
            (_OCDID, _OTHER),
        )
        await cur.execute(
            "DELETE FROM review_sessions WHERE state_code = 'zz'",
        )
        await cur.execute(
            "DELETE FROM people WHERE jurisdiction_ocdid IN (%s, %s)", (_OCDID, _OTHER)
        )
        await cur.execute(
            "DELETE FROM requests WHERE jurisdiction_ocdid IN (%s, %s)", (_OCDID, _OTHER)
        )
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        await cur.execute("DELETE FROM users WHERE email = 'zz-stacked@example.test'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _jurisdiction(ocdid: str = _OCDID, status: str = "active") -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, status)
            VALUES (%s, 'zz', 'local', %s)
            ON CONFLICT (jurisdiction_ocdid) DO UPDATE SET status = EXCLUDED.status
            """,
            (ocdid, status),
        )
        await conn.commit()


async def _request(updated_at: str, ocdid: str = _OCDID) -> str:
    """A pending request whose roster was last touched at `updated_at`.

    `updated_at` is what orders these — whoever last wrote the roster, a scrape or a reviewer.
    `created_at` is left to now() for every row, so only `updated_at` can order them.

    The `pipeline_runs` row exists because every registration path creates one, and both the
    sweep and publish read its `updated_at` to order scrapes.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO requests (request_type, jurisdiction_ocdid, arguments_json, updated_at)
            VALUES ('people', %s, '{}'::jsonb, %s::timestamptz)
            RETURNING id::text
            """,
            (ocdid, updated_at),
        )
        request_id = (await cur.fetchone())[0]
        # One sighting, because `AVAILABLE_FOR_REVIEW` is now "this scrape saw somebody".
        await cur.execute(
            """
            INSERT INTO source_records (request_id, jurisdiction_ocdid, name, label, source_url)
            VALUES (%s, %s, 'Ann Lee', 'Mayor', 'https://zz.gov/council')
            """,
            (request_id, ocdid),
        )
        await cur.execute(
            """
            INSERT INTO pipeline_runs (request_id, status, progress, created_at, updated_at)
            VALUES (%s, 'SUCCESS', 100, %s::timestamptz, %s::timestamptz)
            """,
            (request_id, updated_at, updated_at),
        )
        await conn.commit()
    return request_id


async def _dismissed_at(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT dismissed_at, resolved_by_user_id FROM requests WHERE id::text = %s",
            (request_id,),
        )
        return await cur.fetchone()


async def _hold(request_id: str, status: str, ocdid: str = _OCDID) -> None:
    """Put a request in a reviewer's hands."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (provider, provider_user_id, email)
            VALUES ('test', %s, 'zz-stacked@example.test')
            RETURNING id::text
            """,
            (str(uuid.uuid4()),),
        )
        user_id = (await cur.fetchone())[0]
        await cur.execute(
            """
            INSERT INTO review_sessions (user_id, state_code, daily_goal)
            VALUES (%s, 'zz', 10) RETURNING id::text
            """,
            (user_id,),
        )
        session_id = (await cur.fetchone())[0]
        await cur.execute(
            """
            INSERT INTO review_session_entries
                (review_session_id, jurisdiction_ocdid, status, request_ids)
            VALUES (%s, %s, %s, ARRAY[%s])
            """,
            (session_id, ocdid, status, request_id),
        )
        await conn.commit()


async def _published_request(updated_at: str, ocdid: str = _OCDID) -> str:
    """A request that already went live. No longer a review candidate, but still the newest
    thing anyone said about this jurisdiction."""
    request_id = await _request(updated_at, ocdid)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE requests SET published_at = now() WHERE id::text = %s", (request_id,)
        )
        await conn.commit()
    return request_id


# --- the sweep -----------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_older_card_is_superseded_and_the_newest_survives():
    await _jurisdiction()
    old, new = await _request(_OLD), await _request(_NEW)

    assert await supersede_stacked_requests() == [old]

    old_dismissed, resolved_by = await _dismissed_at(old)
    assert old_dismissed is not None
    assert resolved_by is None  # NULL marks a system sweep, not a person's decision
    assert (await _dismissed_at(new))[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ordering_comes_from_the_roster_not_created_at():
    """The second row inserted carries the older roster — `created_at` would keep the wrong one."""
    await _jurisdiction()
    newer_roster = await _request(_NEW)
    older_roster = await _request(_OLD)

    assert await supersede_stacked_requests() == [older_roster]
    assert (await _dismissed_at(newer_roster))[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_reviewer_edit_does_not_outrank_a_newer_scrape():
    """Ordering asks which scrape read the source more recently, not which row was touched
    more recently. A reviewer correcting the March roster in August did not go and look again;
    the July scrape did, so the March one still loses.

    Work in progress is protected by the held-card exclusion instead, which is time-boxed —
    an edit made and abandoned must not shield a stale roster forever.

    `requests.updated_at` is bumped directly rather than through a save: a save writes
    `assertions` and touches no `requests` column at all now, so what is pinned here is the
    ordering rule — whatever moves that column, ordering ignores it.
    """
    await _jurisdiction()
    edited = await _request(_OLD)
    later_scrape = await _request(_NEW)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE requests SET updated_at = now() WHERE id::text = %s", (edited,)
        )
        await conn.commit()

    assert await supersede_stacked_requests() == [edited]
    assert (await _dismissed_at(later_scrape))[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_single_card_is_never_swept():
    await _jurisdiction()
    only = await _request(_OLD)

    assert await supersede_stacked_requests() == []
    assert (await _dismissed_at(only))[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_jurisdictions_do_not_supersede_each_other():
    await _jurisdiction(_OCDID)
    await _jurisdiction(_OTHER)
    here = await _request(_OLD, _OCDID)
    there = await _request(_NEW, _OTHER)

    assert await supersede_stacked_requests() == []
    assert (await _dismissed_at(here))[0] is None
    assert (await _dismissed_at(there))[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("held_status", ["saved", "resolved", "claimed"])
async def test_a_card_a_reviewer_holds_is_not_swept(held_status):
    """Skipped, not dismissed — a later pass picks it up once the hold lapses."""
    await _jurisdiction()
    old, new = await _request(_OLD), await _request(_NEW)
    await _hold(old, held_status)

    assert await supersede_stacked_requests() == []
    assert (await _dismissed_at(old))[0] is None
    assert (await _dismissed_at(new))[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_held_newest_card_shields_the_whole_jurisdiction_for_that_pass():
    """Holding the newest card pauses the sweep for that jurisdiction.

    Safer: if the reviewer dismisses it, the older cards are still there to fall back to.
    """
    await _jurisdiction()
    old, new = await _request(_OLD), await _request(_NEW)
    await _hold(new, "saved")

    assert await supersede_stacked_requests() == []
    assert (await _dismissed_at(old))[0] is None
    assert (await _dismissed_at(new))[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_inactive_jurisdiction_is_left_entirely_alone():
    """No meaningful newest card to keep, so superseding would strand an arbitrary one."""
    await _jurisdiction(status="inactive")
    old, new = await _request(_OLD), await _request(_NEW)

    assert await supersede_stacked_requests() == []
    assert (await _dismissed_at(old))[0] is None
    assert (await _dismissed_at(new))[0] is None


# --- the publish guard ---------------------------------------------------------------------


def _person() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": "Stacked Test Person",
        "jurisdiction_ocdid": _OCDID,
        "office": {"name": "Council Member", "division_ocdid": None},
        "source_urls": [],
        "updated_at": _MID,
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_guard_refuses_a_roster_older_than_one_already_published():
    """The durable half — a manual re-run bypasses the queue entirely."""
    await _jurisdiction()
    newer, older = await _request(_NEW), await _request(_OLD)

    await publish_request(newer, _OCDID, [{**_person(), "updated_at": _NEW}])

    with pytest.raises(ValueError, match="already published a newer roster"):
        await publish_request(older, _OCDID, [{**_person(), "updated_at": _OLD}])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_guard_permits_republishing_the_same_request():
    """`r.id <> %s` excludes the request being published, so replay stays harmless."""
    await _jurisdiction()
    request_id = await _request(_NEW)
    people = [{**_person(), "updated_at": _NEW}]

    await publish_request(request_id, _OCDID, people)
    await publish_request(request_id, _OCDID, people)  # must not raise


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_guard_permits_a_newer_roster():
    await _jurisdiction()
    older, newer = await _request(_OLD), await _request(_NEW)

    await publish_request(older, _OCDID, [{**_person(), "updated_at": _OLD}])
    await publish_request(newer, _OCDID, [{**_person(), "updated_at": _NEW}])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_draft_older_than_a_published_roster_is_superseded():
    """What can supersede is not the same set as what can be superseded. Comparing candidates
    only to each other left every draft older than a publish in the pool forever — manchester
    TN carried one from May, overtaken ten minutes later, still there in August."""
    await _jurisdiction()
    stale = await _request(_OLD)
    published = await _published_request(_NEW)

    assert await supersede_stacked_requests() == [stale]

    assert (await _dismissed_at(stale))[0] is not None
    # The publish is untouched: it is a supersedor, never a candidate.
    assert (await _dismissed_at(published))[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_draft_newer_than_a_published_roster_survives():
    """The publish is older, so it supersedes nothing. A draft carrying fresher observations
    is the whole reason someone would scrape again after publishing."""
    await _jurisdiction()
    await _published_request(_OLD)
    fresher = await _request(_NEW)

    assert await supersede_stacked_requests() == []
    assert (await _dismissed_at(fresher))[0] is None
