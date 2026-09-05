from unittest.mock import AsyncMock, patch

import pytest

from schemas.common import Jurisdiction
from services.jurisdiction_scrape_candidate import get_scrape_candidates

STATE = "wa"


def _juris(ocdid):
    return Jurisdiction(id=ocdid, name=ocdid, url=f"https://{ocdid}")


def _patch(stale, open_pr=None, active_job=None, pending_issue=None):
    return (
        patch(
            "services.jurisdiction_scrape_candidate.jurisdictions_db.get_stale_jurisdictions",
            new_callable=AsyncMock, return_value=stale,
        ),
        patch(
            "services.jurisdiction_scrape_candidate.review_pool_db.jurisdiction_ocdids_with_open_changesets",
            new_callable=AsyncMock, return_value=open_pr or set(),
        ),
        patch(
            "services.jurisdiction_scrape_candidate.pipeline_runs_db.jurisdiction_ocdids_with_unfinished_runs",
            new_callable=AsyncMock, return_value=active_job or set(),
        ),
        patch(
            "services.jurisdiction_scrape_candidate.issues_db.jurisdiction_ocdids_with_pending_issues",
            new_callable=AsyncMock, return_value=pending_issue or set(),
        ),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_excludes_open_pr_active_job_and_pending_issue():
    stale = [_juris("a"), _juris("b"), _juris("c"), _juris("d")]
    stale_p, pr_p, job_p, issue_p = _patch(
        stale, open_pr={"a"}, active_job={"b"}, pending_issue={"c"}
    )
    with stale_p, pr_p, job_p, issue_p:
        result = await get_scrape_candidates(STATE, 10)

    assert [j.id for j in result] == ["d"]  # the three excluded sets are removed


@pytest.mark.unit
@pytest.mark.asyncio
async def test_caps_at_num_jurisdictions_preserving_order():
    stale = [_juris("a"), _juris("b"), _juris("c")]  # DB already orders never-scraped first
    stale_p, pr_p, job_p, issue_p = _patch(stale)
    with stale_p, pr_p, job_p, issue_p:
        result = await get_scrape_candidates(STATE, 2)

    assert [j.id for j in result] == ["a", "b"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_when_nothing_stale():
    stale_p, pr_p, job_p, issue_p = _patch([])
    with stale_p, pr_p, job_p, issue_p:
        result = await get_scrape_candidates(STATE, 5)

    assert result == []
