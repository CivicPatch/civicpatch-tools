"""A run's start and end, as activity rows.

Real Postgres: `register_run`'s ON CONFLICT DO NOTHING and `apply_pipeline_run_status`'s
already-finished guard both decide whether a second write happens at all, which a mocked
connection cannot honestly exercise.

Isolation: sentinel state 'zy', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.changesets import register_scrape_changeset
from database.database import get_pool
from database.pipeline_runs import register_run
from services.pipeline_runs import apply_pipeline_run_status
from shared.utils.statuses import ActivityType, PipelineRunStatus
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zy/place:zy_activity/government"


async def _activity_rows(ocdid: str) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type, changeset_id::text FROM activity "
            "WHERE jurisdiction_ocdid = %s ORDER BY created_at",
            (ocdid,),
        )
        return [{"type": row[0], "changeset_id": row[1]} for row in await cur.fetchall()]


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    await factories.seed_jurisdiction(_OCDID, "zy")
    yield
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_starting_a_run_logs_a_pipeline_run_start():
    await factories.start_run(_OCDID)

    rows = await _activity_rows(_OCDID)

    assert rows == [{"type": ActivityType.PIPELINE_RUN_START.value, "changeset_id": None}]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_registering_the_same_run_twice_logs_only_one_start():
    run_id = await factories.start_run(_OCDID)
    # The idempotent path production actually uses for a retried trigger.
    await register_run(run_id, _OCDID, {}, if_not_exists=True)

    rows = await _activity_rows(_OCDID)

    assert len(rows) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_that_fails_logs_a_pipeline_run_end_with_no_changeset():
    run_id = await factories.start_run(_OCDID)

    await apply_pipeline_run_status(run_id, PipelineRunStatus.ERROR.value, None, _OCDID)

    rows = await _activity_rows(_OCDID)
    assert rows[-1] == {"type": ActivityType.PIPELINE_RUN_END.value, "changeset_id": None}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_that_reaches_ingest_logs_a_pipeline_run_end_with_its_changeset():
    run_id = await factories.start_run(_OCDID)
    # Mint the changeset the way ingest does (see factories.complete_run), then report success
    # through the service layer directly — that layer is what logs PIPELINE_RUN_END, and
    # reporting it twice (once via a factory, once here) would hit apply_pipeline_run_status's
    # own already-finished guard and never reach the write this test is checking.
    changeset_id = await register_scrape_changeset(run_id)

    await apply_pipeline_run_status(run_id, PipelineRunStatus.SUCCESS.value, None, _OCDID)

    rows = await _activity_rows(_OCDID)
    assert rows[-1] == {"type": ActivityType.PIPELINE_RUN_END.value, "changeset_id": changeset_id}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_non_final_status_logs_no_pipeline_run_end():
    run_id = await factories.start_run(_OCDID)

    await apply_pipeline_run_status(run_id, "running", 50, _OCDID)

    rows = await _activity_rows(_OCDID)
    assert rows == [{"type": ActivityType.PIPELINE_RUN_START.value, "changeset_id": None}]
