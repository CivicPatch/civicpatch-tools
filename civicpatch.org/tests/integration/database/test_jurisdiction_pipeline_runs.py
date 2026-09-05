"""A jurisdiction's attempts, including the ones that proposed nothing.

Real Postgres: the point of this read is a LEFT JOIN to `issues` on the run's own id, and the
absence of a changeset — neither of which a unit test can exercise honestly.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.database import get_pool
from database.issues import upsert_issue
from database.pipeline_runs import get_pipeline_runs_for_jurisdiction
from shared.utils.statuses import PipelineIssueType, PipelineRunErrorType
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_runs/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM issues WHERE issue_key IN ("
            "  SELECT id::text FROM pipeline_runs WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        await cur.execute(
            "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    await factories.seed_jurisdiction(_OCDID, "zz")
    yield
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_that_proposed_nothing_is_still_this_jurisdictions_run():
    """The Arden case. Every other read reaches a run through `changeset_id`, so this run was
    visible while in flight and vanished the moment it finished."""
    run_id = await factories.start_run(_OCDID)
    await factories.fail_run(run_id)

    runs = await get_pipeline_runs_for_jurisdiction(_OCDID)

    assert [r.pipeline_run_id for r in runs] == [run_id]
    assert runs[0].changeset_id is None
    assert runs[0].is_running is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_reason_it_ended_comes_back_with_it():
    run_id = await factories.start_run(_OCDID)
    await factories.fail_run(run_id)
    await upsert_issue(run_id, PipelineRunErrorType.NO_ROSTER_FOUND, [{}])

    runs = await get_pipeline_runs_for_jurisdiction(_OCDID)

    assert runs[0].issue_type == PipelineRunErrorType.NO_ROSTER_FOUND


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_successful_run_carries_the_proposal_it_minted():
    run_id = await factories.start_run(_OCDID)
    changeset_id = await factories.complete_run(run_id)

    runs = await get_pipeline_runs_for_jurisdiction(_OCDID)

    assert runs[0].changeset_id == changeset_id
    assert runs[0].issue_type is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_in_flight_reports_its_progress():
    run_id = await factories.start_run(_OCDID, progress=27)

    runs = await get_pipeline_runs_for_jurisdiction(_OCDID)

    assert runs[0].is_running is True
    assert runs[0].progress == 27


@pytest.mark.integration
@pytest.mark.asyncio
async def test_newest_first_and_capped():
    ids = [await factories.start_run(_OCDID) for _ in range(3)]
    for run_id in ids:
        await factories.fail_run(run_id)

    runs = await get_pipeline_runs_for_jurisdiction(_OCDID, limit=2)

    assert len(runs) == 2
    assert [r.pipeline_run_id for r in runs] == list(reversed(ids))[:2]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_another_jurisdictions_runs_are_not_borrowed():
    other = "ocd-jurisdiction/country:us/state:zz/place:zz_runs_other/government"
    await factories.seed_jurisdiction(other, "zz")
    try:
        await factories.fail_run(await factories.start_run(other))
        mine = await factories.start_run(_OCDID)

        runs = await get_pipeline_runs_for_jurisdiction(_OCDID)

        assert [r.pipeline_run_id for r in runs] == [mine]
    finally:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (other,)
            )
            await cur.execute(
                "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (other,)
            )
            await conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_issue_about_a_changeset_is_not_mistaken_for_the_runs():
    """The join is on the run's own id. A changeset-keyed issue belongs to the proposal."""
    run_id = await factories.start_run(_OCDID)
    changeset_id = await factories.complete_run(run_id)
    await upsert_issue(changeset_id, PipelineIssueType.USER_REPORTED, [{}])

    runs = await get_pipeline_runs_for_jurisdiction(_OCDID)

    assert runs[0].issue_type is None
