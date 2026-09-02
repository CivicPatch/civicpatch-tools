from unittest.mock import AsyncMock, patch

import pytest

from core.coverage import Bucket
from schemas.common import StateJurisdictionSets
from services.coverage import get_municipality_list, get_state_coverage

STATE = "wa"


def _row(ocdid, **overrides):
    return {
        "jurisdiction_ocdid": ocdid,
        "name": ocdid,
        "status": "fresh",
        "officials_count": 1,
        "last_verified_at": "2026-04-01T00:00:00+00:00",
        **overrides,
    }


def _patch(rows, open_pr=None):
    return (
        patch(
            "services.coverage.coverage_db.get_municipality_rows_for_state",
            new_callable=AsyncMock, return_value=rows,
        ),
        patch(
            "services.coverage.review_pool_db.open_ocdids_by_state",
            new_callable=AsyncMock, return_value=open_pr or set(),
        ),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_marks_needs_review_for_ocdids_with_open_prs():
    rows = [_row("a"), _row("b"), _row("c")]
    rows_p, pr_p = _patch(rows, open_pr={"b"})
    with rows_p, pr_p:
        result = await get_municipality_list(STATE)

    assert [(r["jurisdiction_ocdid"], r["needs_review"]) for r in result] == [
        ("a", False),
        ("b", True),
        ("c", False),
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_preserves_row_fields_alongside_needs_review():
    rows = [_row("a", status="stale", officials_count=4)]
    rows_p, pr_p = _patch(rows)
    with rows_p, pr_p:
        result = await get_municipality_list(STATE)

    assert result == [
        {
            "jurisdiction_ocdid": "a",
            "name": "a",
            "status": "stale",
            "officials_count": 4,
            "last_verified_at": "2026-04-01T00:00:00+00:00",
            "needs_review": False,
        }
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_when_no_municipalities():
    rows_p, pr_p = _patch([])
    with rows_p, pr_p:
        result = await get_municipality_list(STATE)

    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_state_coverage_scopes_pipeline_and_issue_lookups_by_state():
    sets = StateJurisdictionSets(
        total={"a", "b"}, scrapeable={"a", "b"}, covered_fresh={"a"}, covered_stale=set(),
    )
    with (
        patch(
            "services.coverage.jurisdictions_db.get_state_jurisdiction_sets",
            new_callable=AsyncMock, return_value=sets,
        ),
        patch(
            "services.coverage.review_pool_db.open_ocdids_by_state",
            new_callable=AsyncMock, return_value=set(),
        ) as to_review_mock,
        patch(
            "services.coverage.pipeline_runs_db.get_active_pipeline_run_jurisdiction_ocdids_by_state",
            new_callable=AsyncMock, return_value={"b"},
        ) as scraping_mock,
        patch(
            "services.coverage.issues_db.get_pending_issue_ocdids_by_state",
            new_callable=AsyncMock, return_value=set(),
        ) as blocked_mock,
    ):
        result = await get_state_coverage(STATE)

    scraping_mock.assert_awaited_once_with(STATE)
    blocked_mock.assert_awaited_once_with(STATE)
    to_review_mock.assert_awaited_once_with(STATE)
    assert result.covered_fresh == 1
    assert result.buckets[Bucket.SCRAPING] == 1
