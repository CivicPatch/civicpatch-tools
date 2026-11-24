"""When a state's pipeline schedule fires. Pure, so it tests without a Temporal client."""

from datetime import date, datetime, timedelta, timezone

from shared.utils.statuses import PipelineRunKind

# Not the workflow instance id (`people-collector-state-{state}`) — Temporal conflates them in its UI.
_SCHEDULE_ID_MARK = "-state-schedule-"

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def schedule_id(kind: PipelineRunKind, state: str) -> str:
    return f"{kind.replace('_', '-')}{_SCHEDULE_ID_MARK}{state}"


def is_state_schedule(schedule_id_: str) -> bool:
    return _SCHEDULE_ID_MARK in schedule_id_


# Sep 1 at 30 days gives Sep 1, Oct 1, Nov 1 — and Aug 2 before that. Not a start date.
def interval_offset(cadence_anchor: date | None, every: timedelta) -> timedelta:
    if cadence_anchor is None:
        return timedelta(0)
    start = datetime(
        cadence_anchor.year,
        cadence_anchor.month,
        cadence_anchor.day,
        tzinfo=timezone.utc,
    )
    return (start - _EPOCH) % every


# Computed, not read back from Temporal: same arithmetic, no round-trip per state.
def next_run_at(
    cadence_days: int | None, cadence_anchor: date | None, now: datetime
) -> datetime | None:
    if cadence_days is None:
        return None
    every = timedelta(days=cadence_days)
    offset = interval_offset(cadence_anchor, every)
    elapsed = now - (_EPOCH + offset)
    periods = elapsed // every
    return _EPOCH + offset + (periods + 1) * every
