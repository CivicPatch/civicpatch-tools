"""When a state's scrape schedule fires, as arithmetic.

Pure, and separate from `lib/temporal/schedules.py` so the offset can be tested without a
Temporal client. The ids live here too: they are a naming convention two places have to agree
on — whoever declares a schedule and whoever decides what to retire — and a convention held in
one function cannot drift between them.
"""

from datetime import date, datetime, timedelta, timezone

# Distinct from the workflow instance id (`state-scrape-{state}`) on purpose: a schedule and the
# workflow it starts are different objects, and Temporal will happily let you name them the same
# thing and then confuse the two in its own UI.
_SCHEDULE_ID_PREFIX = "state-scrape-schedule-"

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def schedule_id(state: str) -> str:
    return f"{_SCHEDULE_ID_PREFIX}{state}"


def is_state_schedule(schedule_id_: str) -> bool:
    return schedule_id_.startswith(_SCHEDULE_ID_PREFIX)


def interval_offset(cadence_start: date | None, every: timedelta) -> timedelta:
    """Where in the cycle this state sits.

    A Temporal interval schedule fires at `epoch + n*every + offset`, so the offset is what
    staggers fifty states instead of firing them all at the same midnight — which would put
    every state's whole candidate pool into the queue at once.

    No start date means no offset: the state fires on the raw interval boundary. That is a
    fine default for one state and a poor one for fifty, which is why the form asks.
    """
    if cadence_start is None:
        return timedelta(0)
    start = datetime(
        cadence_start.year, cadence_start.month, cadence_start.day, tzinfo=timezone.utc
    )
    return (start - _EPOCH) % every
