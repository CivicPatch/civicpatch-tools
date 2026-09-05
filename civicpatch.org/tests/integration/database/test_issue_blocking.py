"""Which jurisdictions a pending issue keeps out of the scrape pool.

Real DB: the thing under test is a join between `issues` and `changesets`, and the bug it
replaces was a missing condition in that join.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

import database.issues as issues_db
from database.database import get_pool
from database.publications import dismiss_request
from shared.utils.statuses import DismissalReason, PipelineIssueType
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_blocking/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM issues WHERE EXISTS ("
            "SELECT 1 FROM changesets c WHERE c.id::text = ANY(issues.changeset_ids) "
            "AND c.jurisdiction_ocdid = %s)",
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


async def _changeset_with_a_pending_issue() -> str:
    changeset_id = await factories.complete_run(await factories.start_run(_OCDID))
    await issues_db.upsert_issue(
        changeset_id, PipelineIssueType.PIPELINE_ERROR, [{"detail": "boom"}]
    )
    return changeset_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_issue_on_an_open_changeset_blocks_its_jurisdiction():
    await _changeset_with_a_pending_issue()

    assert _OCDID in await issues_db.jurisdiction_ocdids_with_pending_issues()
    assert _OCDID in await issues_db.jurisdiction_ocdids_with_pending_issues_in_state("zz")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_resolving_the_changeset_unblocks_it_even_with_the_issue_still_open():
    """The bug this replaces. A pending issue on a terminal changeset froze its jurisdiction
    forever: nothing could re-scrape it, so no run could finish, so
    `supersede_prior_jurisdiction_issues` — which fires only from `finalize_pipeline_run` —
    never cleared the issue. The issue blocked the scrape that would have resolved it.

    Measured 2026-09-05: all 15 pending issues in dev sat on terminal changesets, freezing 10
    jurisdictions."""
    changeset_id = await _changeset_with_a_pending_issue()
    await dismiss_request(changeset_id, DismissalReason.REJECTED)

    assert _OCDID not in await issues_db.jurisdiction_ocdids_with_pending_issues()
    assert _OCDID not in await issues_db.jurisdiction_ocdids_with_pending_issues_in_state("zz")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_both_readers_agree():
    """`jurisdiction_ocdids_with_pending_issues` gates scrape candidates; the by-state one feeds the coverage
    page's `blocked` count, which means blocked *from scraping*. If they disagreed the page
    would report a block that no longer exists."""
    await _changeset_with_a_pending_issue()
    everywhere = await issues_db.jurisdiction_ocdids_with_pending_issues()
    in_zz = await issues_db.jurisdiction_ocdids_with_pending_issues_in_state("zz")

    assert {o for o in everywhere if "state:zz" in o} == in_zz
