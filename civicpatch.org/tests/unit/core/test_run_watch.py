"""Pure — whether a watched scrape has gone quiet. No mocks."""

from datetime import timedelta

import pytest

from core.run_watch import RunWatch, is_quiet, observe

_QUIET_AFTER = timedelta(minutes=30)


@pytest.mark.unit
def test_a_new_report_restarts_the_clock():
    watch = observe(RunWatch(last_report="SCRAPE_PAGE:10", changed_at=0), "SCRAPE_PAGE:11", 1_000)

    assert watch.changed_at == 1_000


@pytest.mark.unit
def test_the_same_report_again_does_not():
    """A run repeating itself is not making progress."""
    watch = observe(RunWatch(last_report="SCRAPE_PAGE:10", changed_at=0), "SCRAPE_PAGE:10", 1_000)

    assert watch.changed_at == 0


@pytest.mark.unit
def test_quiet_only_past_the_threshold():
    watch = RunWatch(last_report="SCRAPE_PAGE:10", changed_at=0)

    assert not is_quiet(watch, _QUIET_AFTER.total_seconds(), _QUIET_AFTER)
    assert is_quiet(watch, _QUIET_AFTER.total_seconds() + 1, _QUIET_AFTER)


@pytest.mark.unit
def test_a_watch_survives_the_heartbeat_round_trip():
    """What a worker restart hands back: the clock resumes rather than resetting."""
    watch = RunWatch(last_report="SCRAPE_PAGE:10", changed_at=123.5)

    assert RunWatch(**watch.model_dump()) == watch
