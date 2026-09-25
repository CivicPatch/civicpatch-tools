"""The assertion lifecycle. Pure — bools in, a state out, no mocks."""

import pytest

from core.claim_lifecycle import (
    TRANSITIONS,
    ClaimEvent,
    ClaimState,
    state_of,
    states_accepting,
)


@pytest.mark.unit
def test_a_row_is_active_unless_withdrawn_or_superseded():
    assert state_of(withdrawn=False, superseded=False) == ClaimState.ACTIVE
    assert state_of(withdrawn=False, superseded=True) == ClaimState.SUPERSEDED
    assert state_of(withdrawn=True, superseded=False) == ClaimState.WITHDRAWN


@pytest.mark.unit
def test_withdrawn_wins_over_superseded():
    """A row can be both — superseded by a newer claim, then also explicitly withdrawn. The
    stamp is the one fact that survives being un-derived: `withdrawn_at` doesn't stop being
    true just because something else also passed it."""
    assert state_of(withdrawn=True, superseded=True) == ClaimState.WITHDRAWN


@pytest.mark.unit
def test_only_an_active_claim_accepts_withdraw():
    """What `withdraw()`'s guard is generated from. A superseded claim isn't the current
    answer, so withdrawing it would record a falsehood; an already-withdrawn one has nothing
    left to stamp."""
    assert states_accepting(ClaimEvent.WITHDRAW) == frozenset({ClaimState.ACTIVE})


@pytest.mark.unit
def test_only_a_withdrawn_claim_accepts_restore():
    assert states_accepting(ClaimEvent.RESTORE) == frozenset({ClaimState.WITHDRAWN})


# Every (state, event) that is deliberately not an edge. A pair in neither this set nor
# `TRANSITIONS` is an oversight, and that is what the test below catches.
NOT_A_TRANSITION = {
    # A superseded claim isn't the current answer — withdrawing it would misrepresent what
    # happened, and restoring it isn't legal since it was never withdrawn.
    (ClaimState.SUPERSEDED, ClaimEvent.WITHDRAW),
    (ClaimState.SUPERSEDED, ClaimEvent.RESTORE),
    # Already withdrawn: withdrawing again has nothing left to stamp.
    (ClaimState.WITHDRAWN, ClaimEvent.WITHDRAW),
    # Already active: nothing withdrawn to restore.
    (ClaimState.ACTIVE, ClaimEvent.RESTORE),
}


@pytest.mark.unit
def test_every_pair_is_declared_or_denied():
    """Totality, which is what makes adding a state or an event safe.

    Add either and every new pair has to be classified — declared as an edge or listed above as
    deliberately not one — before this passes. Silence is not an answer.
    """
    declared = {(t.frm, t.event) for t in TRANSITIONS}
    every_pair = {(s, e) for s in ClaimState for e in ClaimEvent}

    assert declared | NOT_A_TRANSITION == every_pair, (
        "unclassified: " + str(every_pair - declared - NOT_A_TRANSITION)
    )
    assert not (declared & NOT_A_TRANSITION), "a pair is both an edge and denied"
