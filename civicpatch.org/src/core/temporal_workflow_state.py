"""What a running workflow is doing, reduced to the line a maintainer needs.

Pure — takes Temporal's description and returns a summary. No client, no I/O, so the
interesting part (what a stuck run looks like) is testable without a Temporal server.

Only rendered while a scrape is in flight and never stored: a workflow that has finished has
nothing to say that `pipeline_runs.status` does not already say better.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class TemporalWorkflowState:
    """The current activity and how it is going.

    `attempt` is 1 for a healthy run and climbs while something retries — which is the whole
    reason this is worth surfacing. A run stuck on attempt 7 looks identical to a healthy one
    from `pipeline_runs.status` alone: both say RUNNING.
    """

    activity: str | None
    attempt: int
    retrying: bool
    next_retry_seconds: int | None
    last_failure: str | None


HEALTHY_ATTEMPT = 1


def summarize(pending_activities: list[dict], now: datetime) -> TemporalWorkflowState | None:
    """Reduce Temporal's pending activities to the one worth showing.

    Returns None when nothing is pending — a workflow between activities, which is a blink
    rather than a state, and rendering it would flicker.

    The most-retried activity wins when several are pending. A healthy activity beside a
    failing one is not the news; the failing one is.
    """
    if not pending_activities:
        return None

    worst = max(pending_activities, key=lambda a: a.get("attempt") or HEALTHY_ATTEMPT)
    attempt = worst.get("attempt") or HEALTHY_ATTEMPT

    return TemporalWorkflowState(
        activity=worst.get("activity_type"),
        attempt=attempt,
        retrying=attempt > HEALTHY_ATTEMPT,
        next_retry_seconds=_seconds_until(worst.get("scheduled_time"), now),
        last_failure=_failure_message(worst.get("last_failure")),
    )


def _seconds_until(scheduled: datetime | None, now: datetime) -> int | None:
    """How long until the next attempt. None when it is due now or already past — a countdown
    that has expired is noise, and a negative one reads as a bug."""
    if scheduled is None:
        return None
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    remaining = (scheduled - now).total_seconds()
    return int(remaining) if remaining > 0 else None


def _failure_message(failure) -> str | None:
    """The reason the last attempt failed, as a single line.

    Temporal nests the cause; the outer message is usually the wrapper ("Activity task
    failed"), so an inner cause is preferred when present.
    """
    if failure is None:
        return None
    cause = getattr(failure, "cause", None)
    message = getattr(cause, "message", None) or getattr(failure, "message", None)
    return str(message).strip() or None if message else None
