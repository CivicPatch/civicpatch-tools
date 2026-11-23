from decimal import Decimal

import pytest

from runners.pipeline03_people_collector.constants import CRAWL_TIME_BUDGET_S
from runners.pipeline03_people_collector.schemas import OrganizationProgress, PeopleCollectorState, PeopleCollectorStep, ProgressState
from runners.pipeline03_people_collector.transitions.crawl_page_transition import (
    STOP_COST_CAP,
    STOP_MAX_PAGES,
    STOP_MESSAGES,
    STOP_TIME_BUDGET,
    next_crawl_state,
    run_report,
    should_stop_for_time_budget,
)
from shared.schemas import PipelineRunLimits


def _next(**kwargs):
    """`elapsed_seconds` is required in production and irrelevant to most cases here."""
    kwargs.setdefault("elapsed_seconds", 0)
    return next_crawl_state(**kwargs)


def _limits(max_pages=10, cap="1.00"):
    return PipelineRunLimits(max_pages=max_pages, pipeline_run_cap_usd=Decimal(cap))


def _progress(current_data=0, required_data=5, has_target_roles=False, has_target_divisions=False):
    return ProgressState(
        current_data=current_data,
        required_data=required_data,
        has_target_roles=has_target_roles,
        has_target_divisions=has_target_divisions,
    )


def _met_progress():
    return _progress(current_data=5, required_data=5, has_target_roles=True, has_target_divisions=True)


# ── data requirement met ──────────────────────────────────────────────────────

def test_data_requirement_met_is_success():
    state, error = _next(
        processed_count=3,
        current_cost=Decimal("0.50"),
        limits=_limits(),
        progress=_met_progress(),
    )
    assert state == PeopleCollectorStep.CLEANUP
    assert error is None


def test_data_requirement_met_overrides_cap():
    state, error = _next(
        processed_count=3,
        current_cost=Decimal("2.00"),  # over limit
        limits=_limits(cap="1.00"),
        progress=_met_progress(),
    )
    assert state == PeopleCollectorStep.CLEANUP
    assert error is None


def test_data_requirement_met_overrides_max_pages():
    state, error = _next(
        processed_count=20,  # over max
        current_cost=Decimal("0.10"),
        limits=_limits(max_pages=10),
        progress=_met_progress(),
    )
    assert state == PeopleCollectorStep.CLEANUP
    assert error is None


# ── cost limit ────────────────────────────────────────────────────────────────

def test_cap_without_data_proceeds_to_merge():
    """Verified that the stop was reported with a message naming the cause. It now verifies the
    stop is reported with a *reason* identifying the cause, because the cost-cap reason has to
    reach the reviewer as an issue — deciding that by matching a log string would be worse."""
    state, reason = _next(
        processed_count=3,
        current_cost=Decimal("1.00"),  # at limit
        limits=_limits(cap="1.00"),
        progress=_progress(),
    )
    assert state == PeopleCollectorStep.CLEANUP
    assert reason == STOP_COST_CAP
    assert "Cost limit" in STOP_MESSAGES[reason]


# ── max pages ─────────────────────────────────────────────────────────────────

def test_max_pages_without_data_is_failure():
    """Same change as the cost-cap test above, and the same reason: a reason rather than a
    message. Max pages stays log-only — it is not an issue — so this pins that the two stops
    remain distinguishable."""
    state, reason = _next(
        processed_count=15,  # 10 max_pages + 5 required_data = 15
        current_cost=Decimal("0.10"),
        limits=_limits(max_pages=10),
        progress=_progress(required_data=5),
    )
    assert state == PeopleCollectorStep.CLEANUP
    assert reason == STOP_MAX_PAGES
    assert reason != STOP_COST_CAP


# ── continue scraping ─────────────────────────────────────────────────────────

def test_no_stop_condition_continues_scrape():
    state, error = _next(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(max_pages=10, cap="1.00"),
        progress=_progress(current_data=2, required_data=5),
    )
    assert state == PeopleCollectorStep.CRAWL_PAGE
    assert error is None


# ── the roster we hold is an expectation, not a fact ──────────────────────────


def test_one_short_of_the_expected_roster_still_stops():
    """Seattle, 2026-08-17: 10 found against 11 expected, because a member had left office.
    Both target flags were satisfied and the run still crawled to its page cap chasing a
    person who no longer exists."""
    state, error = _next(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(),
        progress=_progress(
            current_data=4,
            required_data=5,
            has_target_roles=True,
            has_target_divisions=True,
        ),
    )
    assert state == PeopleCollectorStep.CLEANUP
    assert error is None


def test_two_short_still_stops():
    """Two is the tolerance: a roster can lose a couple of members between scrapes without
    the expectation becoming unreachable."""
    state, _ = _next(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(),
        progress=_progress(
            current_data=3,
            required_data=5,
            has_target_roles=True,
            has_target_divisions=True,
        ),
    )
    assert state == PeopleCollectorStep.CLEANUP


def test_three_short_keeps_scraping():
    """Beyond the tolerance this is a roster we have not found yet, not a stale expectation."""
    state, _ = _next(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(),
        progress=_progress(
            current_data=2,
            required_data=5,
            has_target_roles=True,
            has_target_divisions=True,
        ),
    )
    assert state == PeopleCollectorStep.CRAWL_PAGE


def test_tolerance_does_not_bypass_the_target_flags():
    """Being one short is forgiven; missing the mayor is not."""
    state, _ = _next(
        processed_count=3,
        current_cost=Decimal("0.10"),
        limits=_limits(),
        progress=_progress(
            current_data=4,
            required_data=5,
            has_target_roles=False,
            has_target_divisions=True,
        ),
    )
    assert state == PeopleCollectorStep.CRAWL_PAGE


# ── several organizations: each is done on its own count ──────────────────────


def _organizations_state(council_found: int, mayor_found: int):
    """Council of 10 and a one-post Office of the Mayor. The flat fields are deliberately far
    from met — with organizations present, they must not decide."""
    progress = ProgressState(
        current_data=0,
        required_data=50,
        organizations=[
            OrganizationProgress(organization_id="council", required=10, found=council_found),
            OrganizationProgress(organization_id="mayor", required=1, found=mayor_found),
        ],
    )
    state, _ = _next(
        processed_count=3, current_cost=Decimal("0.10"), limits=_limits(), progress=progress
    )
    return state


def test_every_organization_done_stops_the_crawl():
    assert _organizations_state(council_found=10, mayor_found=1) == PeopleCollectorStep.CLEANUP


def test_a_complete_council_does_not_stop_the_crawl_while_the_mayor_is_missing():
    """Seattle, 2026-08-17: a flat count read "Council complete, Mayor missing" as nearly done and
    crawled council pages to the cap looking for someone who was never on one."""
    assert _organizations_state(council_found=10, mayor_found=0) == PeopleCollectorStep.CRAWL_PAGE


def test_a_large_organization_is_done_short_of_every_member():
    assert _organizations_state(council_found=8, mayor_found=1) == PeopleCollectorStep.CLEANUP
    assert _organizations_state(council_found=7, mayor_found=1) == PeopleCollectorStep.CRAWL_PAGE


# ── the cap has to be visible outside the container log ───────────────────────


def test_a_capped_run_reports_the_cap_for_the_reviewer_to_see():
    """The gap this closes: the stop was a `logger.warning` and nothing else, so a run that
    hit its ceiling and one that found an empty page looked identical from outside."""
    assert run_report(STOP_COST_CAP, ProgressState()).stopped_at_cost_cap


def test_stopping_at_the_page_limit_is_not_reported():
    """Pages are a crawl bound, not a spend one — it is normal to reach it."""
    assert not run_report(STOP_MAX_PAGES, ProgressState()).stopped_at_cost_cap


# ── the crawl has to fit the job it runs in ───────────────────────────────────

# A crawl needs a clock of its own: its page budget must fit inside the job that runs it.
TIME_BUDGET_SECONDS = 30 * 60


def test_the_crawl_stops_when_its_time_budget_is_spent():
    assert should_stop_for_time_budget(
        elapsed_seconds=TIME_BUDGET_SECONDS, budget_seconds=TIME_BUDGET_SECONDS
    )


def test_the_crawl_keeps_going_until_the_budget_is_spent():
    assert not should_stop_for_time_budget(
        elapsed_seconds=TIME_BUDGET_SECONDS - 1, budget_seconds=TIME_BUDGET_SECONDS
    )


def test_spent_time_and_unmet_requirements_stop_the_crawl():
    state, reason = _next(
        processed_count=15,
        current_cost=Decimal("0.00"),
        limits=_limits(max_pages=15),
        progress=_progress(current_data=8, required_data=9),
        elapsed_seconds=TIME_BUDGET_SECONDS,
    )

    assert (state, reason) == (PeopleCollectorStep.CLEANUP, STOP_TIME_BUDGET)


def test_time_left_keeps_the_crawl_running():
    state, reason = _next(
        processed_count=15,
        current_cost=Decimal("0.00"),
        limits=_limits(max_pages=24),
        progress=_progress(current_data=8, required_data=9),
        elapsed_seconds=60,
    )

    assert (state, reason) == (PeopleCollectorStep.CRAWL_PAGE, None)


def test_finding_what_it_came_for_still_beats_the_clock():
    """A run that is done is done: the budget explains an early stop, it does not invent one."""
    state, reason = _next(
        processed_count=2,
        current_cost=Decimal("0.00"),
        limits=_limits(),
        progress=_met_progress(),
        elapsed_seconds=TIME_BUDGET_SECONDS * 2,
    )

    assert (state, reason) == (PeopleCollectorStep.CLEANUP, None)


def test_a_run_that_spent_its_money_says_that_and_not_the_clock():
    """Money is the harder ceiling and the one the reviewer is billed for."""
    state, reason = _next(
        processed_count=15,
        current_cost=Decimal("1.00"),
        limits=_limits(cap="1.00"),
        progress=_progress(),
        elapsed_seconds=TIME_BUDGET_SECONDS,
    )

    assert (state, reason) == (PeopleCollectorStep.CLEANUP, STOP_COST_CAP)


def test_stopping_on_the_clock_is_not_reported():
    """Like the page bound: a crawl that ran out of time is not a spend problem."""
    assert not run_report(STOP_TIME_BUDGET, ProgressState()).stopped_at_cost_cap


def test_a_crawl_whose_pages_fail_still_stops_on_the_clock():
    """A crawl whose pages all fail never processes one, so nothing but the clock can end it."""
    assert next_crawl_state(
        processed_count=0,
        current_cost=Decimal("0"),
        limits=_limits(),
        progress=_progress(),
        elapsed_seconds=CRAWL_TIME_BUDGET_S,
    ) == (PeopleCollectorStep.CLEANUP, STOP_TIME_BUDGET)
