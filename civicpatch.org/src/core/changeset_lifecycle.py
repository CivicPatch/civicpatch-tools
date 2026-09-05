"""The changeset lifecycle, as a state machine.

Pure — no cursor, no clock. Callers pass in whatever context a rule needs.

**The edge is the unit.** A transition carries its own qualifiers, rather than a state carrying
them in a parallel map. Keyed by state, adding a state meant touching several dicts and hoping;
here it means adding rows. `publish_is_verified` and per-edge effects, both queued in
`.scratch/2026-09-05-plan-autopublish-and-supersede.md`, become fields rather than maps — and
the publish edges are where that earns itself, since `PUBLISHED`, `AUTO_PUBLISHED` and
`DISPLACED` all land in the same state and differ only in what they verify and write.

**A qualifier that cannot reject is not a qualifier.** `reasons` was deleted on 2026-09-05 for
holding the whole `DismissalReason` enum — see `Transition`.

What the machine is for: what a changeset is *in* was written out by hand in SQL across three
modules, each expression free to disagree with this one. `database/changesets.py` now derives
`PUBLISHED`, `RESOLVED` and `WORK_IN_FLIGHT` from `ChangesetState` instead, and
`mark_dismissed` guards its UPDATE with `states_accepting_dismissal` rather than restating the
rule. `AVAILABLE_FOR_REVIEW`, `SWEEPABLE`, `RUN_IN_FLIGHT` and `HELD_BY_REVIEWER` stay in SQL:
they join other tables, so they are eligibility predicates, not states of a changeset.
"""

from dataclasses import dataclass
from enum import StrEnum

from shared.utils.statuses import ChangesetKind


class ChangesetState(StrEnum):
    """Where a changeset is.

    Three, not five. `RUNNING` and `FAILED` described the *run*, back when one row was both; a
    changeset is now minted only by a run that succeeded, so it is born with content to review.

    `OPEN`, settled by migration 178. `RequestReviewStatus` held a second copy of this
    vocabulary saying 'pending' and is gone. 'pending' lost because `issues.status` already
    means something else by it, and the two appear in one sentence constantly: an *open*
    changeset with *pending* issues. 'open' is the word this table is named after — an OSM
    changeset is open or closed — and it is the complement of the `RESOLVED` predicate that
    already exists. 'ready' fails on its own terms: the two hand-edit kinds are born published
    and never are.
    """

    OPEN = "open"
    PUBLISHED = "published"
    DISMISSED = "dismissed"


class ChangesetEvent(StrEnum):
    """What happens to one. Named for the event, not the column it moves."""

    PUBLISHED = "published"
    DISMISSED = "dismissed"


@dataclass(frozen=True)
class Transition:
    """One edge. Qualifiers belong here rather than in a map beside the machine — but only
    qualifiers that can actually reject something.

    `reasons: frozenset[DismissalReason]` lived here until 2026-09-05 and was deleted: it held
    the *entire* enum, so it could never reject, and `states_accepting_dismissal` returned
    `('open',)` whatever it was asked. The fact it was reaching for — a failed run must not be
    labelled a human rejection — is keyed on the **run's** status, not the changeset's state,
    and `core.pipeline_runs.dismissal_for` already models it there.
    """

    frm: ChangesetState
    event: ChangesetEvent
    to: ChangesetState


# Every legal edge. A pair absent from this tuple is not a transition — `advance` returns None
# rather than guessing, and `test_every_pair_is_declared_or_denied` fails if a pair is neither
# here nor in that test's explicit deny-list.
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
}


def advance(state: ChangesetState, event: ChangesetEvent) -> ChangesetState | None:
    """The next state, or None when the event does not apply.

    None rather than an exception: callers ask this to decide, and a scrape reporting after it
    was cancelled is ordinary rather than exceptional.
    """
    for transition in TRANSITIONS:
        if transition.frm is state and transition.event is event:
            return transition.to
    return None


def is_terminal(state: ChangesetState) -> bool:
    """Nothing leaves it. Derived rather than declared — a second `TERMINAL` set beside the
    edges is one more thing that can disagree with them."""
    for transition in TRANSITIONS:
        if transition.frm is state:
            return False
    return True


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
