from decimal import Decimal

import pytest

from runners.people_collector.schemas import PipelineStatus, ProgressState
from runners.people_collector.transitions.process_page_content_transition import (
    next_process_content_state,
)
from shared.schemas import JobConfig


def _job_config(max_pages=10, cost_limit="1.00"):
    return JobConfig(max_pages=max_pages, pipeline_run_cost_limit=Decimal(cost_limit))


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
        job_config=_job_config(),
        progress=_met_progress(),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is None


def test_data_requirement_met_overrides_cost_limit():
    state, error = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("2.00"),  # over limit
        job_config=_job_config(cost_limit="1.00"),
        progress=_met_progress(),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is None


def test_data_requirement_met_overrides_max_pages():
    state, error = next_process_content_state(
        processed_count=20,  # over max
        current_cost=Decimal("0.10"),
        job_config=_job_config(max_pages=10),
        progress=_met_progress(),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is None


# ── cost limit ────────────────────────────────────────────────────────────────

def test_cost_limit_without_data_proceeds_to_merge():
    state, error = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("1.00"),  # at limit
        job_config=_job_config(cost_limit="1.00"),
        progress=_progress(),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is not None
    assert "Cost limit" in error


# ── max pages ─────────────────────────────────────────────────────────────────

def test_max_pages_without_data_is_failure():
    state, error = next_process_content_state(
        processed_count=15,  # 10 max_pages + 5 required_data = 15
        current_cost=Decimal("0.10"),
        job_config=_job_config(max_pages=10),
        progress=_progress(required_data=5),
    )
    assert state == PipelineStatus.CLEANUP
    assert error is not None
    assert "Max pages" in error


# ── continue scraping ─────────────────────────────────────────────────────────

def test_no_stop_condition_continues_scrape():
    state, error = next_process_content_state(
        processed_count=3,
        current_cost=Decimal("0.10"),
        job_config=_job_config(max_pages=10, cost_limit="1.00"),
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
        job_config=_job_config(),
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
        job_config=_job_config(),
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
        job_config=_job_config(),
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
        job_config=_job_config(),
        progress=_progress(
            current_data=4,
            required_data=5,
            has_target_role=False,
            has_target_divisions=True,
        ),
    )
    assert state == PipelineStatus.SCRAPE_PAGE
