"""Dismissing a page's worth of issues in one call.

Real DB: the point is `rowcount` across two tables and the `pending` guard, which a mock
cursor cannot answer honestly.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio
from psycopg import sql

import database.issues as issues_db
from database.database import get_pool
from shared.utils.statuses import PipelineIssueStatus, PipelineIssueType
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_bulk/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
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


async def _one_of_each() -> tuple[str, str]:
    """One of each, so both statements have something to match."""
    run_id = await factories.start_run(_OCDID)
    changeset_id = await factories.complete_run(run_id)
    await issues_db.upsert_issue(
        run_id, PipelineIssueType.PIPELINE_ERROR, [{"error": "boom"}]
    )
    reported_id = await issues_db.create_user_reported_issue(
        changeset_id, "wrong seat", "not on the council", "", 0, "someone"
    )
    run_issue = await _pending_run_issue_id(run_id)
    return run_issue, reported_id


async def _pending_run_issue_id(run_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM pipeline_run_issues WHERE pipeline_run_id = %s",
            (run_id,),
        )
        row = await cur.fetchone()
    assert row
    return row[0]


async def _status(issue_id: str, table: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT status FROM {} WHERE id = %s").format(sql.Identifier(table)),
            (issue_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_one_call_settles_issues_from_both_tables():
    """The endpoint takes bare ids and does not ask which table they came from."""
    run_issue_id, reported_id = await _one_of_each()

    assert await issues_db.resolve_issues([run_issue_id, reported_id]) == 2

    assert await _status(run_issue_id, "pipeline_run_issues") == PipelineIssueStatus.RESOLVED
    assert await _status(reported_id, "changeset_issues") == PipelineIssueStatus.RESOLVED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_already_settled_issue_is_not_counted_again():
    """Two people dismissing one page is ordinary, so the second call reports what it moved."""
    run_issue_id, _ = await _one_of_each()
    await issues_db.resolve_issues([run_issue_id])

    assert await issues_db.resolve_issues([run_issue_id]) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_ids_touches_nothing():
    run_issue_id, _ = await _one_of_each()

    assert await issues_db.resolve_issues([]) == 0
    assert await _status(run_issue_id, "pipeline_run_issues") == PipelineIssueStatus.PENDING
