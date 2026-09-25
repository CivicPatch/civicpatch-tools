"""What varies by changeset kind, and the vocabulary for where a changeset is.

Pure — no cursor, no clock.

**Publishing does not vary by kind.** There is no `ChangesetKind` branch in `services/publish.py`
or `database/publications.py`: a scrape and a hand edit differ in what facts they filed, not in
how they publish. So if you came here looking for "what happens when this kind publishes", the
answer is that the four tables below are the whole of it, and the rest is uniform.

**Why the state vocabulary lives here.** `changeset_state` is a generated column, and what a
changeset is *in* used to be written out by hand in SQL across three modules, each expression
free to disagree with the others. `database/changeset_predicates.py` now derives `RESOLVED` and
`WORK_IN_FLIGHT` from `ChangesetState`, and `mark_dismissed` guards its UPDATE with
`states_accepting` rather than restating the rule in a second language.

`AVAILABLE_FOR_REVIEW`, `SWEEPABLE`, `RUN_IN_FLIGHT` and `HELD_BY_REVIEWER` stay in SQL: they
join other tables, so they are eligibility predicates, not states of a changeset.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from shared.utils.statuses import ChangesetKind


class ChangesetState(StrEnum):
    """Where a changeset is. Three, not five: `RUNNING` and `FAILED` described the *run*, back
    when one row was both."""

    OPEN = "open"
    PUBLISHED = "published"
    DISMISSED = "dismissed"


class ChangesetEvent(StrEnum):
    """What happens to one. Named for the event, not the column it moves."""

    PUBLISHED = "published"
    DISMISSED = "dismissed"


@dataclass(frozen=True)
class Transition:
    """One edge: which state an event may leave, and where it lands."""

    frm: ChangesetState
    event: ChangesetEvent
    to: ChangesetState


# Every legal edge. Two, because there are only two ways out of `OPEN` and nothing leaves the
# states they land in. `test_every_pair_is_declared_or_denied` fails if a pair is neither here
# nor in that test's explicit deny-list.
TRANSITIONS: tuple[Transition, ...] = (
    Transition(ChangesetState.OPEN, ChangesetEvent.PUBLISHED, ChangesetState.PUBLISHED),
    # A human read the roster and said no, a newer one won, or the run that produced it never
    # finished. The database checks the *vocabulary* of `dismissed_reason`
    # (`changesets_dismissed_reason_valid`) but cannot check that the reason fits the edge.
    Transition(
        ChangesetState.OPEN,
        ChangesetEvent.DISMISSED,
        ChangesetState.DISMISSED,
    ),
)


# Where a kind begins. Pinned against the four `register_*` functions by
# `test_every_kind_is_born_where_INITIAL_STATE_says`.
INITIAL_STATE: dict[ChangesetKind, ChangesetState] = {
    ChangesetKind.SCRAPE: ChangesetState.OPEN,
    ChangesetKind.SHEET_IMPORT: ChangesetState.OPEN,
    ChangesetKind.PEOPLE_EDIT: ChangesetState.PUBLISHED,
    ChangesetKind.JURISDICTION_EDIT: ChangesetState.PUBLISHED,
    # Open, so its withdraws stay inert (R3) until publishing marks it and rebuilds the
    # projection in one transaction. See `register_rollback_changeset`.
    ChangesetKind.ROLLBACK: ChangesetState.OPEN,
}


# The kinds the review pool offers and the review card may publish. A sheet import is decided on
# its own batch page only, so it is not one of them.
REVIEW_POOL_KINDS: frozenset[ChangesetKind] = frozenset({ChangesetKind.SCRAPE})

# Kinds whose sightings state only the fields they fill: a blank cell means "no information",
# not "clear it", so the proposal keeps the published value. A scrape states a whole page.
PARTIAL_KINDS: frozenset[ChangesetKind] = frozenset({ChangesetKind.SHEET_IMPORT})

# How long a sheet import may wait on its batch page before the reaper dismisses it as expired.
UNPUBLISHED_IMPORT_MAX_AGE = timedelta(days=7)


def states_accepting(event: ChangesetEvent) -> tuple[str, ...]:
    """Which states this event may leave, as `changesets.changeset_state` values.

    `mark_dismissed` guards its UPDATE with this instead of restating the rule in SQL. A
    hand-written `published_at IS NULL AND dismissed_at IS NULL` is this same fact in a second
    language, free to disagree with it; generating the guard means the machine decides and the
    statement stays atomic, so nothing has to read-then-write and lose a race to a concurrent
    publish.

    An event no state accepts yields `()`, which matches no row — the safe outcome, and one
    the caller needs no exception to handle.
    """
    accepting = []
    for transition in TRANSITIONS:
        if transition.event is event:
            accepting.append(transition.frm.value)
    return tuple(accepting)
