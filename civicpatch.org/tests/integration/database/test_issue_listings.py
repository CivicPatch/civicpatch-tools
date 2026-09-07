"""What each issues-page section reads, filtered by state.

Real DB: the listings join `jurisdictions` on top of their anchor table, so the state filter's
column must be qualified — spelled bare it parses and only fails at execution.

Isolation: sentinel state 'zz', cleaned before and after each test. Containment assertions, not
counts: other files seed into 'zz' too.
"""

import pytest
import pytest_asyncio

import database.issue_listings as listings_db
import database.issues as issues_db
from database.database import get_pool
from shared.utils.statuses import PipelineIssueType
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_listings/government"
_STATE = "zz"


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
    await factories.seed_jurisdiction(_OCDID, _STATE, "Zz Listings")
    yield
    await _wipe()


async def _seed_both() -> tuple[str, str]:
    run_id = await factories.start_run(_OCDID)
    changeset_id = await factories.complete_run(run_id)
    await issues_db.upsert_issue(
        run_id, PipelineIssueType.PIPELINE_ERROR, [{"error": "boom"}]
    )
    reported_id = await issues_db.create_user_reported_issue(
        changeset_id, "wrong seat", "not on the council", "", 0, "someone"
    )
    return run_id, reported_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_filtered_pipeline_listing_finds_its_run():
    run_id, _ = await _seed_both()

    rows, total = await listings_db.get_pipeline_run_issues_page(
        [], page=1, per_page=50, state_code=_STATE
    )

    assert total >= 1
    mine = [r for r in rows if r["pipeline_run_id"] == run_id]
    assert len(mine) == 1
    assert mine[0]["issue_type"] == PipelineIssueType.PIPELINE_ERROR
    assert mine[0]["jurisdictions"] == [
        {
            "jurisdiction_ocdid": _OCDID,
            "name": "Zz Listings",
            "state": _STATE,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_filtered_reported_listing_finds_its_changeset():
    _, reported_id = await _seed_both()

    rows, total = await listings_db.get_changeset_issues_page(
        [], page=1, per_page=50, state_code=_STATE
    )

    assert total >= 1
    mine = [r for r in rows if r["id"] == reported_id]
    assert len(mine) == 1
    assert mine[0]["data"]["title"] == "wrong seat"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_another_states_filter_excludes_them():
    """Without this, a filter matching everything would still pass the tests above."""
    run_id, reported_id = await _seed_both()

    run_rows, _ = await listings_db.get_pipeline_run_issues_page(
        [], page=1, per_page=50, state_code="zy"
    )
    reported_rows, _ = await listings_db.get_changeset_issues_page(
        [], page=1, per_page=50, state_code="zy"
    )

    assert not [r for r in run_rows if r["pipeline_run_id"] == run_id]
    assert not [r for r in reported_rows if r["id"] == reported_id]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_type_filter_keeps_only_that_type():
    """The `IN` clause. Its previous test filtered on `unrecognized_role`, retired by migration
    179, and asserted `isinstance(rows, list)` — so it matched nothing and passed either way."""
    run_id, _ = await _seed_both()
    await issues_db.upsert_issue(run_id, PipelineIssueType.COST_CAP_REACHED, [{}])

    rows, _ = await listings_db.get_pipeline_run_issues_page(
        [PipelineIssueType.COST_CAP_REACHED], page=1, per_page=50, state_code=_STATE
    )

    mine = [r for r in rows if r["pipeline_run_id"] == run_id]
    assert [r["issue_type"] for r in mine] == [PipelineIssueType.COST_CAP_REACHED]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sort_order_reverses():
    """The `ORDER BY` direction branch, which nothing observed before."""
    run_id, _ = await _seed_both()
    await issues_db.upsert_issue(run_id, PipelineIssueType.COST_CAP_REACHED, [{}])

    newest, _ = await listings_db.get_pipeline_run_issues_page(
        [], page=1, per_page=50, state_code=_STATE, sort_desc=True
    )
    oldest, _ = await listings_db.get_pipeline_run_issues_page(
        [], page=1, per_page=50, state_code=_STATE, sort_desc=False
    )

    # Two rows at minimum, or `reversed` of a one-item list would pass trivially.
    assert len(newest) >= 2
    assert [r["id"] for r in newest] == list(reversed([r["id"] for r in oldest]))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_counts_agree_with_the_listing():
    """The bug's shape: chips reporting rows above a table saying there were none."""
    await _seed_both()

    counts = await listings_db.get_pipeline_run_issue_counts(state_code=_STATE)
    rows, _ = await listings_db.get_pipeline_run_issues_page(
        [], page=1, per_page=200, state_code=_STATE
    )

    assert counts.get(PipelineIssueType.PIPELINE_ERROR) == len(
        [r for r in rows if r["issue_type"] == PipelineIssueType.PIPELINE_ERROR]
    )
