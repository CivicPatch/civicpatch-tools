"""A crawl that ran out of pages short of the roster it expected.

`required_data` is what we already hold, or what research named — an expectation, not a fact.
So the shortfall is reported only past the tolerance the crawler itself allows, or a run that
stopped because it had enough would report that it did not. cp.org files the issue from the report.
"""

from unittest.mock import AsyncMock, MagicMock

from runners.pipeline03_people_collector.constants import DATA_REQUIREMENT_TOLERANCE
import pytest

from runners.pipeline03_people_collector.schemas import FindJurisdictionUrlStep, ProgressState
from runners.pipeline03_people_collector.transitions.main import review_output_transition
from runners.pipeline03_people_collector.transitions.crawl_page_transition import (
    STOP_COST_CAP,
    run_report,
)
from shared.utils.run_reports import Shortfall
from shared.utils.statuses import PipelineRunErrorType, PipelineRunStatus
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit


def _progress(found, expected):
    return ProgressState(
        current_data=found,
        required_data=expected,
        has_target_roles=True,
        has_target_divisions=True,
    )


def test_a_roster_short_of_expectation_reports_the_shortfall():
    short = _progress(3, 3 + DATA_REQUIREMENT_TOLERANCE + 1)

    assert run_report(None, short).shortfall == Shortfall(found=3, expected=6)


def test_a_shortfall_inside_the_tolerance_reports_nothing():
    """Seattle 2026-08-17: 10 found against 11 expected, both flags satisfied. A council that
    lost a member makes its old size permanently unreachable."""
    assert run_report(None, _progress(11 - DATA_REQUIREMENT_TOLERANCE, 11)).shortfall is None


def test_finding_more_than_expected_reports_nothing():
    assert run_report(None, _progress(9, 7)).shortfall is None


def test_a_capped_run_reports_the_cap():
    assert run_report(STOP_COST_CAP, _progress(1, 9)).stopped_at_cost_cap


@pytest.mark.asyncio
async def test_an_empty_roster_is_an_error_and_reports_neither_cap_nor_shortfall():
    """Both can be true at once, and 'found nothing' is the one that explains the other."""
    context = pipeline_run_context_factory(steps={})
    context = context.model_copy(
        update={"data": context.data.model_copy(update={"stop_reason": STOP_COST_CAP, "find_jurisdiction_url_step": FindJurisdictionUrlStep()})}
    )

    next_context, next_state = await review_output_transition(MagicMock(), MagicMock(), context, AsyncMock())

    assert next_state == PipelineRunStatus.SEND_ERROR
    assert next_context.data.error_step == PipelineRunErrorType.NO_ROSTER_FOUND
    assert (next_context.data.stopped_at_cost_cap, next_context.data.shortfall) == (False, None)
