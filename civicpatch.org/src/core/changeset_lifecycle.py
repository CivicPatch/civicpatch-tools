"""The changeset lifecycle, as a state machine.

Modelled on `pipelines/src/runners/people_collector/transitions/main.py`: an explicit map keyed
by state, and a driver that knows nothing about any particular state.

Pure — no cursor, no clock. What a changeset is *in* today is spelled out ten separate times in
SQL (`REVIEW_STATUS`, `WORK_IN_FLIGHT`, `AVAILABLE_FOR_REVIEW`, `RUN_IN_FLIGHT`, `SWEEPABLE`,
`HELD_BY_REVIEWER` in `database/changesets.py`; `RESOLVED` in `database/jurisdictions.py`;
`CONFIRMED`, `FAILED`, `COLLECTED` in `database/changeset_summaries.py`), each a different
combination of `status`, `published_at`, `dismissed_at` and `kind`. This is that machine, named.

What it catches that nothing catches today: dev holds a scrape with a `CANCELLED` run dismissed
as `rejected`, and one with an `ERROR` run dismissed as `cancelled`. A human cannot reject a run
that produced no roster, and an errored run was not cancelled. Both are unreachable here.
"""

from enum import StrEnum

from shared.utils.statuses import ChangesetKind, DismissalReason


class ChangesetState(StrEnum):
    """Where a changeset is.

    Three, not five. `RUNNING` and `FAILED` described the *run*, back when one row was both; a
    changeset is now minted only by a run that succeeded, so it is born with content to review.
    """

    READY = "ready"
    PUBLISHED = "published"
    DISMISSED = "dismissed"


class ChangesetEvent(StrEnum):
    """What happens to one. Named for the event, not the column it moves."""

    PUBLISHED = "published"
    DISMISSED = "dismissed"


TERMINAL = frozenset({ChangesetState.PUBLISHED, ChangesetState.DISMISSED})

# Keyed by state, like the pipeline's transition map. A pair absent from a state's row is not a
# transition — `advance` returns None rather than guessing.
TRANSITIONS: dict[ChangesetState, dict[ChangesetEvent, ChangesetState]] = {
    ChangesetState.READY: {
        ChangesetEvent.PUBLISHED: ChangesetState.PUBLISHED,
        ChangesetEvent.DISMISSED: ChangesetState.DISMISSED,
    },
    ChangesetState.PUBLISHED: {},
    ChangesetState.DISMISSED: {},
}

# Which reasons a dismissal may carry, by the state it leaves. This is the pair the database
# does not constrain: `changesets_dismissed_reason_valid` checks the vocabulary but not whether
# the reason fits the run, which is how `CANCELLED`/`rejected` got written.
DISMISSAL_REASONS: dict[ChangesetState, frozenset[DismissalReason]] = {
    # A human read a roster and said no, or a newer one won. A roster that was re-confirmed
    # publishes instead — it is a decision, not a dismissal.
    # A human read a roster and said no, or a newer one won; or the sweep gave up on the run
    # that produced it.
    ChangesetState.READY: frozenset(
        {
            DismissalReason.REJECTED,
            DismissalReason.SUPERSEDED,
            DismissalReason.ERRORED,
            DismissalReason.CANCELLED,
        }
    ),
}

# Where a kind begins.
INITIAL_STATE: dict[ChangesetKind, ChangesetState] = {
    ChangesetKind.SCRAPE: ChangesetState.READY,
    ChangesetKind.SHEET_IMPORT: ChangesetState.READY,
    ChangesetKind.PEOPLE_EDIT: ChangesetState.PUBLISHED,
    ChangesetKind.JURISDICTION_EDIT: ChangesetState.PUBLISHED,
}

def advance(state: ChangesetState, event: ChangesetEvent) -> ChangesetState | None:
    """The next state, or None when the event does not apply.

    None rather than an exception: callers ask this to decide, and a scrape reporting after it
    was cancelled is ordinary rather than exceptional.
    """
    return TRANSITIONS[state].get(event)


def states_accepting_dismissal(reason: DismissalReason) -> tuple[str, ...]:
    """Which states a dismissal for this reason may leave, as `changesets.state` values.

    The caller guards its UPDATE with this instead of restating the rule in SQL. A hand-written
    `published_at IS NULL AND dismissed_at IS NULL` is this same fact in a second language, free
    to disagree with it; generating the guard means the machine decides and the statement stays
    atomic, so nothing has to read-then-write and lose a race to a concurrent publish.

    A reason legal from no state yields `()`, which matches no row — the safe outcome, and one
    the caller needs no exception to handle.
    """
    return tuple(
        state.value
        for state, events in TRANSITIONS.items()
        if ChangesetEvent.DISMISSED in events and dismissal_is_legal(state, reason)
    )


def is_terminal(state: ChangesetState) -> bool:
    return state in TERMINAL


def dismissal_is_legal(state: ChangesetState, reason: DismissalReason) -> bool:
    """Whether a dismissal for this reason may leave this state.

    """
    return reason in DISMISSAL_REASONS.get(state, frozenset())
