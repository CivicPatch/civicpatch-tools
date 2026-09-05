"""The invariant that has to survive the requests/pipeline_runs refactor.

A run is an attempt and a changeset is what it proposed. `pipeline_runs.changeset_id` is
nullable and only set at ingest, so the two have **different ids** and a run may have no
changeset at all. Nothing obliges their statuses to agree, and that gap is where the phantom
scrapes came from: a run ended, the proposal stayed `pending` forever, and the jurisdiction page
listed it and disabled editing from that same set.

So this pins the rule rather than the implementation: **once a run reaches a state it will not
leave, what it proposed is no longer pending work.** Built through `factories`, which drives the
real writers — the fixture here used to give the run and the changeset one id, which is the
shape only migration 169's backfill ever produced, and it hid three separate readers that broke
on real rows.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from database.database import get_pool
from database.changesets import get_in_flight, register_scrape_changeset, register_scrape_changeset
from services import pipeline_runs as run_lifecycle
from shared.utils.statuses import PipelineRunStatus, TERMINAL_PIPELINE_RUN_STATUSES
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_runstatus/government"

# A terminal run that produced a roster leaves work behind; one that did not, does not.
_PRODUCES_SOMETHING = {"SUCCESS", "RESOLVED"}


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
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
    """An attempt that has not reached ingest, so it has proposed nothing yet."""
    await factories.seed_jurisdiction(_OCDID, "zz")
    return await factories.start_run(_OCDID, status=PipelineRunStatus.RUNNING)


async def _a_run_with_a_proposal() -> tuple[str, str]:
    """A run that reached ingest. Two ids, as production gives them."""
    run_id = await _a_run_in_flight()
    return run_id, await register_scrape_changeset(run_id)


async def _is_still_pending_work(changeset_id: str) -> bool:
    """The question the jurisdiction page asks, and the edit blocker reads from."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT published_at IS NULL AND dismissed_at IS NULL FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        return (await cur.fetchone())[0]


async def _apply(run_id: str, status: str) -> None:
    # Redis is a real process boundary; the DB is not, and the DB is what this asserts on.
    with patch(
        "services.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock
    ):
        await run_lifecycle.apply_pipeline_run_status(
            pipeline_run_id=run_id, status=status, progress=None, jurisdiction_ocdid=_OCDID
        )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("status", sorted(TERMINAL_PIPELINE_RUN_STATUSES))
async def test_a_terminal_run_never_leaves_its_request_pending_without_a_reason(status):
    """Every terminal status, not a hand-picked two — a new one added to the enum shows up here
    automatically rather than quietly inheriting whichever branch it falls into."""
    run_id, changeset_id = await _a_run_with_a_proposal()

    await _apply(run_id, status)

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
    run_id, changeset_id = await _a_run_with_a_proposal()

    await _apply(run_id, "RUNNING")

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
    run_id, _ = await _a_run_with_a_proposal()

    before = await get_in_flight(_OCDID)
    assert [entry.is_running for entry in before.in_flight] == [True]

    await _apply(run_id, status)

    after = await get_in_flight(_OCDID)
    assert [entry.is_running for entry in after.in_flight] == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_that_errors_after_ingest_settles_the_changeset_it_minted():
    """Built through the real writers, so the ids differ the way production's now do.

    `register_scrape_changeset` mints a fresh uuid; the run keeps its own. Every "settle the
    request" call above is handed the run's id, and `mark_dismissed` matches `changesets.id`.
    The fixtures in this file share one id, so they cannot tell the two apart.
    """
    await factories.seed_jurisdiction(_OCDID, "zz")
    run_id = await factories.start_run(_OCDID)
    changeset_id = await register_scrape_changeset(run_id)
    assert changeset_id != run_id

    await _apply(run_id, PipelineRunStatus.ERROR.value)

    assert await _is_still_pending_work(changeset_id) is False


# --- the stuck-run sweeper ---------------------------------------------------------


async def _set_run(run_id: str, status: str, age_hours: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            # `finished_at` alongside a terminal status, because that is the only pairing the
            # app writes — `update_pipeline_run_status` sets them together, and the expiry sweep
            # asks `finished_at IS NULL` rather than matching a list of terminal names.
            "UPDATE pipeline_runs SET status = %s, "
            "finished_at = CASE WHEN %s = ANY(%s) THEN NOW() ELSE NULL END, "
            "updated_at = NOW() - make_interval(hours => %s) WHERE id = %s",
            (
                status,
                status,
                [s.value for s in TERMINAL_PIPELINE_RUN_STATUSES],
                age_hours,
                run_id,
            ),
        )
        await conn.commit()


async def _status(run_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT status FROM pipeline_runs WHERE id = %s", (run_id,)
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

    run_id = await _a_run_in_flight()
    await _set_run(run_id, "SCRAPE_PAGE", age_hours=48)

    expired = await expire_stale_pipeline_runs(timedelta(hours=6))

    # It proposed nothing, so the sweep reports the attempt and no changeset to settle.
    assert [(run.pipeline_run_id, run.changeset_id) for run in expired] == [(run_id, None)]
    assert await _status(run_id) == "ERROR"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_terminal_run_is_left_alone():
    """SUCCESS is an answer, however old. Rewriting it to ERROR would lose a publish."""
    from datetime import timedelta

    from database.pipeline_runs import expire_stale_pipeline_runs

    run_id = await _a_run_in_flight()
    await _set_run(run_id, "SUCCESS", age_hours=48)

    expired = await expire_stale_pipeline_runs(timedelta(hours=6))
    assert run_id not in [run.pipeline_run_id for run in expired]
    assert await _status(run_id) == "SUCCESS"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_still_reporting_is_left_alone():
    """Mid-scrape, not stuck. The age is the whole distinction."""
    from datetime import timedelta

    from database.pipeline_runs import expire_stale_pipeline_runs

    run_id = await _a_run_in_flight()
    await _set_run(run_id, "SCRAPE_PAGE", age_hours=1)

    expired = await expire_stale_pipeline_runs(timedelta(hours=6))
    assert run_id not in [run.pipeline_run_id for run in expired]
    assert await _status(run_id) == "SCRAPE_PAGE"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_cancelled_run_reads_as_cancelled_from_its_dismissal():
    """The pipeline engine polls this every loop and checks one thing: `== CANCELLED`.

    It is answered from `dismissed_reason` rather than `status` so that it survives the column:
    a dismissal is written in a transaction, where the live status is a signal a cache could
    lose, and the run-status plan removes `status` entirely.

    The row here is built by hand because production writes *both* — `cancel` sets the status to
    `CANCELLED` and then dismisses — so today the two always agree and this branch never fires.
    That is the point: it is the shape that has to keep working when only one of them is left.
    """
    from database.pipeline_runs import get_pipeline_run_status

    run_id, changeset_id = await _a_run_with_a_proposal()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET dismissed_at = now(), "
            "dismissed_reason = 'cancelled' WHERE id = %s",
            (changeset_id,),
        )
        await conn.commit()

    reported = await get_pipeline_run_status(run_id)

    assert reported["status"] == "CANCELLED"
