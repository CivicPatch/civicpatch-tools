"""The assertion lifecycle. Pure — bools in, a state out, no mocks."""

import pytest

from core.assertion_lifecycle import (
    TRANSITIONS,
    AssertionEvent,
    AssertionState,
    state_of,
    states_accepting,
)


@pytest.mark.unit
def test_a_row_is_active_unless_withdrawn_or_superseded():
    assert state_of(withdrawn=False, superseded=False) == AssertionState.ACTIVE
    assert state_of(withdrawn=False, superseded=True) == AssertionState.SUPERSEDED
    assert state_of(withdrawn=True, superseded=False) == AssertionState.WITHDRAWN


@pytest.mark.unit
def test_withdrawn_wins_over_superseded():
    """A row can be both — superseded by a newer claim, then also explicitly withdrawn. The
    stamp is the one fact that survives being un-derived: `withdrawn_at` doesn't stop being
    true just because something else also passed it."""
    assert state_of(withdrawn=True, superseded=True) == AssertionState.WITHDRAWN


@pytest.mark.unit
def test_only_an_active_claim_accepts_withdraw():
    """What `withdraw()`'s guard is generated from. A superseded claim isn't the current
    answer, so withdrawing it would record a falsehood; an already-withdrawn one has nothing
    left to stamp."""
    assert states_accepting(AssertionEvent.WITHDRAW) == frozenset({AssertionState.ACTIVE})


@pytest.mark.unit
def test_only_a_withdrawn_claim_accepts_restore():
    assert states_accepting(AssertionEvent.RESTORE) == frozenset({AssertionState.WITHDRAWN})


# Every (state, event) that is deliberately not an edge. A pair in neither this set nor
# `TRANSITIONS` is an oversight, and that is what the test below catches.
NOT_A_TRANSITION = {
    # A superseded claim isn't the current answer — withdrawing it would misrepresent what
    # happened, and restoring it isn't legal since it was never withdrawn.
    (AssertionState.SUPERSEDED, AssertionEvent.WITHDRAW),
    (AssertionState.SUPERSEDED, AssertionEvent.RESTORE),
    # Already withdrawn: withdrawing again has nothing left to stamp.
    (AssertionState.WITHDRAWN, AssertionEvent.WITHDRAW),
    # Already active: nothing withdrawn to restore.
    (AssertionState.ACTIVE, AssertionEvent.RESTORE),
}


@pytest.mark.unit
def test_every_pair_is_declared_or_denied():
    """Totality, which is what makes adding a state or an event safe.

    Add either and every new pair has to be classified — declared as an edge or listed above as
    deliberately not one — before this passes. Silence is not an answer.
    """
    declared = {(t.frm, t.event) for t in TRANSITIONS}
    every_pair = {(s, e) for s in AssertionState for e in AssertionEvent}

    assert declared | NOT_A_TRANSITION == every_pair, (
        "unclassified: " + str(every_pair - declared - NOT_A_TRANSITION)
    )
    assert not (declared & NOT_A_TRANSITION), "a pair is both an edge and denied"
