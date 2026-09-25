from dataclasses import dataclass
from enum import StrEnum


class ClaimState(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class ClaimEvent(StrEnum):
    WITHDRAW = "withdraw"
    RESTORE = "restore"


@dataclass(frozen=True)
class Transition:
    frm: ClaimState
    event: ClaimEvent
    to: ClaimState | None


# Every legal edge. A pair absent from both this tuple and a test's explicit deny-list is an
# oversight, the same shape as `changeset_lifecycle.py`'s own guard test.
TRANSITIONS: tuple[Transition, ...] = (
    # A claim already superseded by a later one is not the current answer, so withdrawing it
    # too would claim a moderator retracted something a later claim had already replaced.
    Transition(
        ClaimState.ACTIVE, ClaimEvent.WITHDRAW, ClaimState.WITHDRAWN
    ),
    Transition(ClaimState.WITHDRAWN, ClaimEvent.RESTORE, None),
)


def state_of(withdrawn: bool, superseded: bool) -> ClaimState:
    if withdrawn:
        return ClaimState.WITHDRAWN
    return ClaimState.SUPERSEDED if superseded else ClaimState.ACTIVE


def states_accepting(event: ClaimEvent) -> frozenset[ClaimState]:
    return frozenset(t.frm for t in TRANSITIONS if t.event is event)
