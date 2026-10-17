"""The pure pieces of `scrape_local`. Starting runs and polling them is exercised by running the
script against the dev stack, not by a mock-heavy unit test."""

import pytest

from scripts.scrape_local import Run, RunState, available_gib, progress_line

pytestmark = pytest.mark.unit

_AROOSTOOK = "ocd-jurisdiction/country:us/state:me/county:aroostook/government"
_TRAVIS = "ocd-jurisdiction/country:us/state:tx/county:travis/government"


def test_available_memory_is_read_in_gib():
    meminfo = "MemTotal:       12245764 kB\nMemAvailable:    3145728 kB\n"

    assert available_gib(meminfo) == 3.0


def test_meminfo_without_the_available_line_is_an_error():
    with pytest.raises(ValueError):
        available_gib("MemTotal:       12245764 kB\n")


def test_progress_names_each_run_and_its_percentage_once_known():
    runs = [Run(run_id="a", jurisdiction_ocdid=_AROOSTOOK), Run(run_id="b", jurisdiction_ocdid=_TRAVIS)]
    states = {"a": RunState(status="RUNNING", finished=False, progress=40)}

    assert progress_line(runs, states) == f"{_AROOSTOOK} 40%, {_TRAVIS}"


def test_progress_with_nothing_running_says_none():
    assert progress_line([], {}) == "none"
