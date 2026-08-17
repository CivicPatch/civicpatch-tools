"""How many people must be placed in a division before the roster counts as division-complete.

`target_divisions` is built from the division_ocdids on the roster already in the database, so
it carries that roster's staleness — a ward renamed, merged or dropped upstream leaves a target
no scrape can ever reach, and the run crawls to its page cap chasing it. Same failure the
required_data tolerance exists for.

Floored at one rather than allowed to reach zero: subtracting a flat tolerance would make the
check vacuous exactly where it matters most, since a jurisdiction with two wards would require
nobody to be placed in either.
"""

import pytest

from runners.people_collector.steps.step_04_process_page_content.process_page_content import (
    DIVISION_REQUIREMENT_TOLERANCE,
    required_division_count,
)


@pytest.mark.unit
def test_no_divisions_expected_requires_none():
    """A jurisdiction with no wards has nothing to place anyone in."""
    assert required_division_count(0) == 0


@pytest.mark.unit
@pytest.mark.parametrize("expected", [1, 2, 3])
def test_small_jurisdictions_still_need_one(expected):
    """The tolerance must never reach zero here — that would pass a run that placed nobody."""
    assert required_division_count(expected) == 1


@pytest.mark.unit
def test_larger_jurisdictions_get_the_full_tolerance():
    assert required_division_count(9) == 9 - DIVISION_REQUIREMENT_TOLERANCE


@pytest.mark.unit
def test_the_requirement_never_exceeds_what_is_expected():
    for expected in range(0, 15):
        assert required_division_count(expected) <= max(expected, 0)
