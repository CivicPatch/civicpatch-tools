from dataclasses import dataclass
from enum import StrEnum


class AssertionState(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class AssertionEvent(StrEnum):
    WITHDRAW = "withdraw"
    RESTORE = "restore"


@dataclass(frozen=True)
class Transition:
    frm: AssertionState
    event: AssertionEvent
    to: AssertionState | None


# Every legal edge. A pair absent from both this tuple and a test's explicit deny-list is an
# oversight, the same shape as `changeset_lifecycle.py`'s own guard test.
TRANSITIONS: tuple[Transition, ...] = (
    # A claim already superseded by a later one is not the current answer, so withdrawing it
    # too would claim a moderator retracted something a later claim had already replaced.
    Transition(
        AssertionState.ACTIVE, AssertionEvent.WITHDRAW, AssertionState.WITHDRAWN
    ),
    Transition(AssertionState.WITHDRAWN, AssertionEvent.RESTORE, None),
)


def state_of(withdrawn: bool, superseded: bool) -> AssertionState:
    if withdrawn:
        return AssertionState.WITHDRAWN
    return AssertionState.SUPERSEDED if superseded else AssertionState.ACTIVE


def states_accepting(event: AssertionEvent) -> frozenset[AssertionState]:
    return frozenset(t.frm for t in TRANSITIONS if t.event is event)
