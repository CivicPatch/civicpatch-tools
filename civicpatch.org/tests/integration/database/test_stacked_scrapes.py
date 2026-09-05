"""Integration tests for the stacked-scrape sweep and the publish guard.

Real Postgres: every guarantee here is a SQL predicate, not Python.
Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio

from database.database import get_pool
from database.users import SYSTEM_USER_ID
from database.pipeline_runs import expire_stale_pipeline_runs
from database.publications import publish_request
from database.changesets import supersede_stacked_requests
from tests.integration import factories

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
            "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid IN (%s, %s)",
            (_OCDID, _OTHER),
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid IN (%s, %s)", (_OCDID, _OTHER)
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
    """A pending proposal whose scrape read the source at `updated_at`.

    Driven through the real writers, so the run and the changeset get the different ids
    production gives them. `created_at` is left to now() for every row, so only `updated_at` can
    order them.
    """
    run_id = await factories.start_run(ocdid)
    changeset_id = await factories.complete_run(run_id)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # One sighting, because `AVAILABLE_FOR_REVIEW` is now "this scrape saw somebody".
        await cur.execute(
            """
            INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label, source_url)
            VALUES (%s, %s, 'Ann Lee', 'Mayor', 'https://zz.gov/council')
            """,
            (changeset_id, ocdid),
        )
        await cur.execute(
            """
            UPDATE changesets SET created_at = %s::timestamptz,
                                  updated_at = %s::timestamptz
            WHERE id::text = %s
            """,
            (updated_at, updated_at, changeset_id),
        )
        # The clock the expiry sweep reads.
        await cur.execute(
            "UPDATE pipeline_runs SET updated_at = %s::timestamptz WHERE id::text = %s",
            (updated_at, run_id),
        )
        await conn.commit()
    return changeset_id


async def _run_for(changeset_id: str) -> str:
    """The attempt behind a proposal — they have had different ids since migration 169."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM pipeline_runs WHERE changeset_id::text = %s",
            (changeset_id,),
        )
        return (await cur.fetchone())[0]


async def _dismissed_at(changeset_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT dismissed_at, resolved_by_user_id FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        return await cur.fetchone()


async def _hold(changeset_id: str, status: str, ocdid: str = _OCDID) -> None:
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
                (review_session_id, jurisdiction_ocdid, status, changeset_ids)
            VALUES (%s, %s, %s, ARRAY[%s])
            """,
            (session_id, ocdid, status, changeset_id),
        )
        await conn.commit()


async def _published_request(updated_at: str, ocdid: str = _OCDID) -> str:
    """A request that already went live. No longer a review candidate, but still the newest
    thing anyone said about this jurisdiction."""
    changeset_id = await _request(updated_at, ocdid)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET published_at = now() WHERE id::text = %s", (changeset_id,)
        )
        await conn.commit()
    return changeset_id


# --- the sweep -----------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_older_card_is_superseded_and_the_newest_survives():
    await _jurisdiction()
    old, new = await _request(_OLD), await _request(_NEW)

    assert await supersede_stacked_requests() == [old]

    old_dismissed, resolved_by = await _dismissed_at(old)
    assert old_dismissed is not None
    # The system, not NULL: migration 160 made a machine resolution an actor rather than
    # an absence, and the supersede sweeps were the last paths still leaving it empty.
    assert str(resolved_by) == SYSTEM_USER_ID
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
async def test_giving_up_on_a_run_does_not_restamp_the_source_clock():
    """Ordering asks which scrape read the source more recently, so only reading the source may
    move `updated_at`. Expiring a run is the one writer that touches a request without reading
    anything — restamp there and a March roster nobody looked at outranks the July scrape.

    This replaces a test that bumped `requests.updated_at` directly. That column went in 147,
    which removed the generic clock a reviewer edit could move; the hazard it guarded now lives
    entirely in this one query.
    """
    await _jurisdiction()
    abandoned = await _request(_OLD)
    await _request(_NEW)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # The fixture stamps SUCCESS, which is terminal. A run only expires while in flight,
        # which `finished_at IS NULL` is what says now.
        await cur.execute(
            "UPDATE pipeline_runs SET status = 'PENDING', finished_at = NULL "
            "WHERE id::text = %s",
            (await _run_for(abandoned),),
        )
        await conn.commit()

    expired = await expire_stale_pipeline_runs(timedelta(days=1))
    assert [run.changeset_id for run in expired] == [abandoned]

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            # The run carries the status; the changeset carries the clock and the dismissal.
            "SELECT run.status, c.updated_at::text, c.dismissed_reason, c.state "
            "FROM changesets c JOIN pipeline_runs run ON run.changeset_id = c.id "
            "WHERE c.id::text = %s",
            (abandoned,),
        )
        status, updated_at, dismissed_reason, state = await cur.fetchone()
    assert status == "ERROR"
    # Settled, not merely labelled. A dead run left unresolved keeps counting in
    # `WORK_IN_FLIGHT`, which is what would block its jurisdiction from ever being scraped
    # again once the status clause compensating for it goes.
    assert dismissed_reason == "errored"
    assert state == "dismissed"
    assert updated_at.startswith("2026-03-01")


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
    changeset_id = await _request(_NEW)
    people = [{**_person(), "updated_at": _NEW}]

    await publish_request(changeset_id, _OCDID, people)
    await publish_request(changeset_id, _OCDID, people)  # must not raise


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
