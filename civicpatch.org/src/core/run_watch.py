"""Whether a scrape being watched has gone quiet.

Pure. The poll activity carries the watch in its heartbeat details, so a worker restart resumes
the clock rather than resetting it — and never counts as the run going quiet.
"""

from datetime import timedelta

from pydantic import BaseModel


class RunWatch(BaseModel):
    last_report: str | None = None
    # Epoch seconds: the watch outlives the process, so a monotonic clock would not survive it.
    changed_at: float


def observe(watch: RunWatch, report: str, now: float) -> RunWatch:
    if report == watch.last_report:
        return watch
    return RunWatch(last_report=report, changed_at=now)


def is_quiet(watch: RunWatch, now: float, quiet_after: timedelta) -> bool:
    return now - watch.changed_at > quiet_after.total_seconds()
