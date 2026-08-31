"""What a running scrape's Temporal state reduces to.

The case worth covering is the stuck run: `changesets.status` says RUNNING whether a scrape
is healthy or has been failing the same activity for an hour, so this summary is the only thing
that tells them apart.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from core.temporal_workflow_state import summarize

NOW = datetime(2026, 8, 17, 18, 0, 0, tzinfo=timezone.utc)


def activity(name="poll_pipeline_run_status", attempt=1, scheduled=None, last_failure=None):
    return {
        "activity_type": name,
        "attempt": attempt,
        "scheduled_time": scheduled,
        "last_failure": last_failure,
    }


@dataclass
class _Failure:
    message: str
    cause: object = None


@pytest.mark.unit
def test_nothing_pending_is_nothing_to_show():
    """A workflow between activities is a blink, not a state — rendering it would flicker."""
    assert summarize([], NOW) is None


@pytest.mark.unit
def test_a_healthy_run_reports_its_activity_and_is_not_retrying():
    state = summarize([activity()], NOW)
    assert state is not None
    assert state.activity == "poll_pipeline_run_status"
    assert state.attempt == 1
    assert state.retrying is False
    assert state.last_failure is None


@pytest.mark.unit
def test_a_stuck_run_reports_the_attempt_and_why():
    """The reason this exists: RUNNING looks identical whether an activity is on attempt 1
    or attempt 7."""
    state = summarize(
        [
            activity(
                name="trigger_github_action",
                attempt=7,
                scheduled=NOW + timedelta(seconds=42),
                last_failure=_Failure("Activity task failed", cause=_Failure("503 from GitHub")),
            )
        ],
        NOW,
    )
    assert state is not None
    assert state.activity == "trigger_github_action"
    assert state.attempt == 7
    assert state.retrying is True
    assert state.next_retry_seconds == 42
    assert state.last_failure == "503 from GitHub"


@pytest.mark.unit
def test_the_failing_activity_wins_when_several_are_pending():
    """A healthy activity beside a failing one is not the news."""
    state = summarize(
        [activity(name="healthy", attempt=1), activity(name="failing", attempt=4)], NOW
    )
    assert state is not None
    assert state.activity == "failing"
    assert state.attempt == 4


@pytest.mark.unit
def test_an_elapsed_retry_time_is_not_a_countdown():
    """A retry scheduled in the past is due now; showing "next in -8s" reads as a bug."""
    state = summarize([activity(attempt=3, scheduled=NOW - timedelta(seconds=8))], NOW)
    assert state is not None
    assert state.next_retry_seconds is None


@pytest.mark.unit
def test_the_wrapper_message_gives_way_to_the_cause():
    """Temporal wraps failures; "Activity task failed" says nothing a maintainer can act on."""
    state = summarize(
        [activity(attempt=2, last_failure=_Failure("Activity task failed", cause=_Failure("boom")))],
        NOW,
    )
    assert state is not None
    assert state.last_failure == "boom"


@pytest.mark.unit
def test_a_naive_scheduled_time_is_read_as_utc():
    """Temporal's protobuf timestamps arrive naive; treating them as local time would make the
    countdown wrong by the offset."""
    state = summarize(
        [activity(attempt=2, scheduled=(NOW + timedelta(seconds=30)).replace(tzinfo=None))], NOW
    )
    assert state is not None
    assert state.next_retry_seconds == 30
