"""The schedule id convention and the stagger arithmetic."""

from datetime import date, datetime, timedelta, timezone

import pytest

from core.scrape_schedule import (
    interval_offset,
    is_state_schedule,
    next_run_at,
    schedule_id,
)

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


# ── when it fires next ────────────────────────────────────────────────────────


def _at(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=timezone.utc)


def test_a_manual_state_has_no_next_run():
    assert next_run_at(None, date(2026, 9, 1), _at(2026, 9, 5)) is None


def test_the_next_run_is_the_first_boundary_after_now():
    """Computed, not asked: the form shows a next run per state without a round-trip each, and
    without being wrong while a schedule is still unconverged."""
    nxt = next_run_at(7, date(2026, 9, 1), _at(2026, 9, 5))

    assert nxt == _at(2026, 9, 8)


def test_a_future_cadence_anchor_sets_the_phase_and_does_not_delay_the_first_run():
    """⚠ `cadence_anchor` is a **phase**, not a start. A Temporal interval schedule fires at
    every `epoch + n*every + offset`; it does not wait for a date. So a December start on a
    30-day cadence fires on the boundary whose phase matches December 1 — which is October 2 —
    and again on November 1, and on December 1.

    This is what `ScheduleIntervalSpec` does, so `next_run_at` matching it is the point. The
    name is the problem, not the behaviour."""
    nxt = next_run_at(30, date(2026, 12, 1), _at(2026, 9, 5))

    assert nxt == _at(2026, 10, 2)
    # ...and December 1 really is on the cycle.
    assert (_at(2026, 12, 1) - nxt) % timedelta(days=30) == timedelta(0)


def test_it_agrees_with_the_offset_used_to_build_the_schedule():
    """The two must not drift: one says when Temporal will fire, the other tells Temporal when
    to fire. Both derive from `interval_offset`, so this pins that they still do."""
    every = timedelta(days=14)
    offset = interval_offset(date(2026, 9, 1), every)
    nxt = next_run_at(14, date(2026, 9, 1), _at(2026, 9, 5))

    assert (nxt - datetime(1970, 1, 1, tzinfo=timezone.utc) - offset) % every == timedelta(0)
