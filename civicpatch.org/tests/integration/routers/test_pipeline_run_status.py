"""The invariant that has to survive the requests/pipeline_runs refactor.

`pipeline_runs.request_id` is UNIQUE and NOT NULL, so a run and a request are one piece of work
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
from routers.api import pipeline_runs as pipeline_runs_router
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_runstatus/government"

# A terminal run that produced a roster leaves work behind; one that did not, does not.
_PRODUCES_SOMETHING = {"SUCCESS", "RESOLVED"}


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM requests WHERE jurisdiction_ocdid = %s", (_OCDID,))
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
            INSERT INTO requests (request_type, jurisdiction_ocdid, arguments_json)
            VALUES ('people', %s, '{}'::jsonb) RETURNING id::text
            """,
            (_OCDID,),
        )
        request_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO pipeline_runs (request_id, status) VALUES (%s, 'RUNNING')",
            (request_id,),
        )
        await conn.commit()
    return request_id


async def _is_still_pending_work(request_id: str) -> bool:
    """The question the jurisdiction page asks, and the edit blocker reads from."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT published_at IS NULL AND dismissed_at IS NULL FROM requests WHERE id::text = %s",
            (request_id,),
        )
        return (await cur.fetchone())[0]


async def _apply(request_id: str, status: str) -> None:
    # Redis is a real process boundary; the DB is not, and the DB is what this asserts on.
    with patch(
        "routers.api.pipeline_runs.pubsub_service.publish", new_callable=AsyncMock
    ):
        await pipeline_runs_router.apply_pipeline_run_status(
            request_id=request_id, status=status, progress=None, jurisdiction_ocdid=_OCDID
        )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("status", sorted(TERMINAL_PIPELINE_RUN_STATUSES))
async def test_a_terminal_run_never_leaves_its_request_pending_without_a_reason(status):
    """Every terminal status, not a hand-picked two — a new one added to the enum shows up here
    automatically rather than quietly inheriting whichever branch it falls into."""
    request_id = await _a_run_in_flight()

    await _apply(request_id, status)

    still_pending = await _is_still_pending_work(request_id)
    assert still_pending == (status in _PRODUCES_SOMETHING), (
        f"{status}: a run that produced nothing must settle its request, and one that "
        f"produced a roster must leave it for review"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_still_going_settles_nothing():
    """The other half of the rule. Progress is not an outcome, and dismissing on one would
    discard a scrape mid-flight."""
    request_id = await _a_run_in_flight()

    await _apply(request_id, "RUNNING")

    assert await _is_still_pending_work(request_id) is True
