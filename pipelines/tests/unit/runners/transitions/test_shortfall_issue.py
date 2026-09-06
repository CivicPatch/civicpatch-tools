"""A crawl that ran out of pages short of the roster it expected.

`required_data` is what we already hold, or what research named — an expectation, not a fact.
So the issue fires only past the tolerance the crawler itself allows, or a run that stopped
because it had enough would file an issue saying it did not.
"""

import pytest

from runners.people_collector.schemas import ProgressState
from runners.people_collector.transitions.main import _collect_pipeline_heuristics
from runners.people_collector.transitions.process_page_content_transition import (
    DATA_REQUIREMENT_TOLERANCE,
    STOP_COST_CAP,
)
from shared.utils.statuses import PipelineIssueType

pytestmark = pytest.mark.unit

_RECORDS = ["a sighting"]


def _progress(found, expected):
    return ProgressState(
        current_data=found,
        required_data=expected,
        has_target_role=True,
        has_target_divisions=True,
    )


def _types(issues):
    return [issue["type"] for issue in issues]


def test_a_roster_short_of_expectation_raises():
    short = _progress(3, 3 + DATA_REQUIREMENT_TOLERANCE + 1)

    _, issues = _collect_pipeline_heuristics(_RECORDS, None, short)

    assert _types(issues) == [PipelineIssueType.FEWER_THAN_EXPECTED]
    assert issues[0]["data"] == {"found": 3, "expected": 6}


def test_a_shortfall_inside_the_tolerance_raises_nothing():
    """Seattle 2026-08-17: 10 found against 11 expected, both flags satisfied. A council that
    lost a member makes its old size permanently unreachable."""
    _, issues = _collect_pipeline_heuristics(
        _RECORDS, None, _progress(11 - DATA_REQUIREMENT_TOLERANCE, 11)
    )

    assert issues == []


def test_finding_more_than_expected_raises_nothing():
    _, issues = _collect_pipeline_heuristics(_RECORDS, None, _progress(9, 7))

    assert issues == []


def test_the_cost_cap_explains_its_own_shortfall():
    """One run, one fact: a capped run is already short and already says so."""
    short = _progress(1, 9)

    _, issues = _collect_pipeline_heuristics(_RECORDS, STOP_COST_CAP, short)

    assert _types(issues) == [PipelineIssueType.COST_CAP_REACHED]


def test_an_empty_roster_still_wins():
    _, issues = _collect_pipeline_heuristics([], None, _progress(0, 9))

    assert issues == []
