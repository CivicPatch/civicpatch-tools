from decimal import Decimal

import pytest

from runners.people_collector.schemas import PipelineStatus, ProgressState
from runners.people_collector.transitions.process_page_content_transition import (
    STOP_COST_CAP,
    STOP_MAX_PAGES,
    STOP_MESSAGES,
    next_process_content_state,
)
from runners.people_collector.transitions.main import _collect_pipeline_heuristics
from shared.schemas import PipelineRunLimits
from shared.utils.statuses import PipelineIssueType, PipelineRunErrorType


def _limits(max_pages=10, cap="1.00"):
    return PipelineRunLimits(max_pages=max_pages, pipeline_run_cap_usd=Decimal(cap))


def _progress(current_data=0, required_data=5, has_target_role=False, has_target_divisions=False):
    return ProgressState(
        current_data=current_data,
        required_data=required_data,
        has_target_role=has_target_role,
        has_target_divisions=has_target_divisions,
    )


def _met_progress():
    return _progress(current_data=5, required_data=5, has_target_role=True, has_target_divisions=True)


# ── data requirement met ──────────────────────────────────────────────────────

def test_data_requirement_met_is_success():
    state, error = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("0.50"),
        limits=_limits(),
        progress=_met_progress(),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is None


def test_data_requirement_met_overrides_cap():
    state, error = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("2.00"),  # over limit
        limits=_limits(cap="1.00"),
        progress=_met_progress(),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is None


def test_data_requirement_met_overrides_max_pages():
    state, error = next_process_content_state(
        processed_count=20,  # over max
        current_cost=Decimal("0.10"),
        limits=_limits(max_pages=10),
        progress=_met_progress(),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is None


# ── cost limit ────────────────────────────────────────────────────────────────

def test_cap_without_data_proceeds_to_merge():
    """Verified that the stop was reported with a message naming the cause. It now verifies the
    stop is reported with a *reason* identifying the cause, because the cost-cap reason has to
    reach the reviewer as an issue — deciding that by matching a log string would be worse."""
    state, reason = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("1.00"),  # at limit
        limits=_limits(cap="1.00"),
        progress=_progress(),
    )
    assert state == PipelineStatus.CLEANUP
    assert reason == STOP_COST_CAP
    assert "Cost limit" in STOP_MESSAGES[reason]


# ── max pages ─────────────────────────────────────────────────────────────────

def test_max_pages_without_data_is_failure():
    """Same change as the cost-cap test above, and the same reason: a reason rather than a
    message. Max pages stays log-only — it is not an issue — so this pins that the two stops
    remain distinguishable."""
    state, reason = next_process_content_state(
        processed_count=15,  # 10 max_pages + 5 required_data = 15
        current_cost=Decimal("0.10"),
        limits=_limits(max_pages=10),
        progress=_progress(required_data=5),
    )
    assert state == PipelineStatus.CLEANUP
    assert reason == STOP_MAX_PAGES
    assert reason != STOP_COST_CAP


# ── continue scraping ─────────────────────────────────────────────────────────

def test_no_stop_condition_continues_scrape():
    state, error = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(max_pages=10, cap="1.00"),
        progress=_progress(current_data=2, required_data=5),
    )
    assert state == PipelineStatus.SCRAPE_PAGE
    assert error is None


# ── the roster we hold is an expectation, not a fact ──────────────────────────


def test_one_short_of_the_expected_roster_still_stops():
    """Seattle, 2026-08-17: 10 found against 11 expected, because a member had left office.
    Both target flags were satisfied and the run still crawled to its page cap chasing a
    person who no longer exists."""
    state, error = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(),
        progress=_progress(
            current_data=4,
            required_data=5,
            has_target_role=True,
            has_target_divisions=True,
        ),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is None


def test_two_short_still_stops():
    """Two is the tolerance: a roster can lose a couple of members between scrapes without
    the expectation becoming unreachable."""
    state, _ = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(),
        progress=_progress(
            current_data=3,
            required_data=5,
            has_target_role=True,
            has_target_divisions=True,
        ),
    )
    assert state == PipelineStatus.CLEANUP


def test_three_short_keeps_scraping():
    """Beyond the tolerance this is a roster we have not found yet, not a stale expectation."""
    state, _ = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(),
        progress=_progress(
            current_data=2,
            required_data=5,
            has_target_role=True,
            has_target_divisions=True,
        ),
    )
    assert state == PipelineStatus.SCRAPE_PAGE


def test_tolerance_does_not_bypass_the_target_flags():
    """Being one short is forgiven; missing the mayor is not."""
    state, _ = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(),
        progress=_progress(
            current_data=4,
            required_data=5,
            has_target_role=False,
            has_target_divisions=True,
        ),
    )
    assert state == PipelineStatus.SCRAPE_PAGE


# ── the cap has to be visible outside the container log ───────────────────────


def test_a_capped_run_reports_an_issue_the_reviewer_can_see():
    """The gap this closes: the stop was a `logger.warning` and nothing else, so a run that
    hit its ceiling and one that found an empty page looked identical from outside."""
    _error, issues = _collect_pipeline_heuristics([{"name": "A"}], STOP_COST_CAP)

    assert [issue["type"] for issue in issues] == [PipelineIssueType.COST_CAP_REACHED]


def test_stopping_at_the_page_limit_is_not_an_issue():
    """Pages are a crawl bound, not a spend one — it is normal to reach it."""
    _error, issues = _collect_pipeline_heuristics([{"name": "A"}], STOP_MAX_PAGES)

    assert issues == []


def test_a_run_that_found_nothing_reports_emptiness_and_not_the_cap():
    """Both can be true at once. Reporting both would put two issues on one run saying the
    same thing twice, and 'found nothing' is the one that explains the other."""
    error, issues = _collect_pipeline_heuristics([], STOP_COST_CAP)

    assert error == PipelineRunErrorType.NO_ROSTER_FOUND
    assert issues == []
