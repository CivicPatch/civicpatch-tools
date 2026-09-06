"""The schedule id convention and the stagger arithmetic."""

from datetime import date, timedelta

import pytest

from core.scrape_schedule import interval_offset, is_state_schedule, schedule_id

pytestmark = pytest.mark.unit


def test_a_state_schedule_is_recognisable_from_its_id_alone():
    """`_retire_undeclared_schedules` deletes anything it does not recognise, so telling a
    state schedule from the five fixed ones cannot depend on reading the database."""
    assert is_state_schedule(schedule_id("wa"))
    assert not is_state_schedule("od-sync")
    assert not is_state_schedule("sweep-changes")


def test_the_schedule_id_is_not_the_workflow_instance_id():
    """Temporal lets you name them the same and then confuses the two in its own UI."""
    assert schedule_id("wa") != "state-scrape-wa"


def test_no_start_date_means_no_offset():
    assert interval_offset(None, timedelta(days=30)) == timedelta(0)


def test_two_states_a_day_apart_stay_a_day_apart():
    """The whole point: fifty states firing at one midnight would queue every candidate pool
    at once."""
    every = timedelta(days=30)
    wa = interval_offset(date(2026, 9, 1), every)
    tn = interval_offset(date(2026, 9, 2), every)
    assert tn - wa == timedelta(days=1)


def test_the_offset_never_exceeds_the_interval():
    """It is a position within the cycle, not a delay — a start date years before or after the
    interval still lands inside one period."""
    every = timedelta(days=7)
    for start in (date(1999, 3, 1), date(2026, 9, 5), date(2031, 12, 25)):
        assert timedelta(0) <= interval_offset(start, every) < every
