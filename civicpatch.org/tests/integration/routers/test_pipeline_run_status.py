"""The invariant that has to survive the requests/pipeline_runs refactor.

`pipeline_runs.changeset_id` is UNIQUE and NOT NULL, so a run and a request are one piece of work
in two tables. Nothing obliges their two statuses to agree, and that gap is where the phantom
scrapes came from: a run ended, the request stayed `pending` forever, and the jurisdiction page
listed it and disabled editing from that same set.

So this pins the rule rather than the implementation: **once a run reaches a state it will not
leave, its request is no longer pending work.** Written against the real DB so it keeps holding
as the code underneath moves.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from database.database import get_pool
from database.changesets import get_in_flight
from routers.api import pipeline_runs as pipeline_runs_router
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_runstatus/government"

# A terminal run that produced a roster leaves work behind; one that did not, does not.
_PRODUCES_SOMETHING = {"SUCCESS", "RESOLVED"}


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _cleanup()
    yield
    await _cleanup()


async def _a_run_in_flight() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid) VALUES (%s)", (_OCDID,)
        )
        await cur.execute(
            """
            INSERT INTO changesets (kind, status, jurisdiction_ocdid, arguments_json)
            VALUES ('scrape', 'SUCCESS', %s, '{}'::jsonb) RETURNING id::text
            """,
            (_OCDID,),
        )
        changeset_id = (await cur.fetchone())[0]
        await cur.execute(
            "UPDATE changesets SET status = 'RUNNING', "
            "sourced_at = CURRENT_TIMESTAMP WHERE id = %s",
            (changeset_id,),
        )
        await conn.commit()
    return changeset_id


async def _is_still_pending_work(changeset_id: str) -> bool:
    """The question the jurisdiction page asks, and the edit blocker reads from."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT published_at IS NULL AND dismissed_at IS NULL FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        return (await cur.fetchone())[0]


async def _apply(changeset_id: str, status: str) -> None:
    # Redis is a real process boundary; the DB is not, and the DB is what this asserts on.
    with patch(
        "routers.api.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock
    ):
        await pipeline_runs_router.apply_pipeline_run_status(
            changeset_id=changeset_id, status=status, progress=None, jurisdiction_ocdid=_OCDID
        )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("status", sorted(TERMINAL_PIPELINE_RUN_STATUSES))
async def test_a_terminal_run_never_leaves_its_request_pending_without_a_reason(status):
    """Every terminal status, not a hand-picked two — a new one added to the enum shows up here
    automatically rather than quietly inheriting whichever branch it falls into."""
    changeset_id = await _a_run_in_flight()

    await _apply(changeset_id, status)

    still_pending = await _is_still_pending_work(changeset_id)
    assert still_pending == (status in _PRODUCES_SOMETHING), (
        f"{status}: a run that produced nothing must settle its request, and one that "
        f"produced a roster must leave it for review"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_still_going_settles_nothing():
    """The other half of the rule. Progress is not an outcome, and dismissing on one would
    discard a scrape mid-flight."""
    changeset_id = await _a_run_in_flight()

    await _apply(changeset_id, "RUNNING")

    assert await _is_still_pending_work(changeset_id) is True


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("status", sorted(TERMINAL_PIPELINE_RUN_STATUSES))
async def test_the_in_flight_row_answers_whether_the_run_is_going(status):
    """The page used to test the raw status against its own copy of the terminal set — one in
    Python, one in JavaScript, free to drift. `is_running` is derived server-side so both sides
    are told the same answer.

    Asked of `get_in_flight`, not the history query. It used to read this off the history row,
    but history is what *happened* — it no longer returns unresolved changesets, and carrying
    `is_running` there meant two queries deriving one fact from the same predicates."""
    changeset_id = await _a_run_in_flight()

    before = await get_in_flight(_OCDID)
    assert [entry.is_running for entry in before.in_flight] == [True]

    await _apply(changeset_id, status)

    after = await get_in_flight(_OCDID)
    assert [entry.is_running for entry in after.in_flight] == []


# --- the stuck-run sweeper ---------------------------------------------------------


async def _set_run(changeset_id: str, status: str, age_hours: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET status = %s, "
            "sourced_at = NOW() - make_interval(hours => %s) WHERE id = %s",
            (status, age_hours, changeset_id),
        )
        await conn.commit()


async def _status(changeset_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT status FROM changesets WHERE id = %s", (changeset_id,)
        )
        return (await cur.fetchone())[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_stuck_on_a_step_is_expired():
    """The case the sweeper exists for, and could not reach until 2026-08-25.

    A running row holds a *step* name — the engine PATCHes `ctx.current_state.value` every
    loop — so matching `status = 'RUNNING'` never found one. A pipeline killed hard sat at
    `SCRAPE_PAGE` forever and `RUN_IN_FLIGHT` kept calling it live.
    """
    from datetime import timedelta

    from database.pipeline_runs import expire_stale_pipeline_runs

    changeset_id = await _a_run_in_flight()
    await _set_run(changeset_id, "SCRAPE_PAGE", age_hours=48)

    expired = await expire_stale_pipeline_runs(timedelta(hours=6))

    assert changeset_id in expired
    assert await _status(changeset_id) == "ERROR"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_terminal_run_is_left_alone():
    """SUCCESS is an answer, however old. Rewriting it to ERROR would lose a publish."""
    from datetime import timedelta

    from database.pipeline_runs import expire_stale_pipeline_runs

    changeset_id = await _a_run_in_flight()
    await _set_run(changeset_id, "SUCCESS", age_hours=48)

    assert changeset_id not in await expire_stale_pipeline_runs(timedelta(hours=6))
    assert await _status(changeset_id) == "SUCCESS"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_still_reporting_is_left_alone():
    """Mid-scrape, not stuck. The age is the whole distinction."""
    from datetime import timedelta

    from database.pipeline_runs import expire_stale_pipeline_runs

    changeset_id = await _a_run_in_flight()
    await _set_run(changeset_id, "SCRAPE_PAGE", age_hours=1)

    assert changeset_id not in await expire_stale_pipeline_runs(timedelta(hours=6))
    assert await _status(changeset_id) == "SCRAPE_PAGE"
