"""The changeset lifecycle. Pure — a state and an event in, a state out, no mocks."""

import pytest

from core.changeset_lifecycle import (
    INITIAL_STATE,
    TRANSITIONS,
    ChangesetEvent,
    ChangesetState,
    advance,
    states_accepting,
    is_terminal,
)
from shared.utils.statuses import ChangesetKind, DismissalReason


@pytest.mark.unit
def test_every_kind_is_born_with_something_to_show():
    """No kind waits on a run any more. A scrape's changeset is minted at ingest by a run that
    already succeeded, so it starts where an import does."""
    assert INITIAL_STATE[ChangesetKind.SCRAPE] == ChangesetState.OPEN
    assert INITIAL_STATE[ChangesetKind.SHEET_IMPORT] == ChangesetState.OPEN
    assert INITIAL_STATE[ChangesetKind.PEOPLE_EDIT] == ChangesetState.PUBLISHED


@pytest.mark.unit
def test_a_reviewable_changeset_publishes_or_is_dismissed():
    assert (
        advance(ChangesetState.OPEN, ChangesetEvent.PUBLISHED)
        == ChangesetState.PUBLISHED
    )
    assert (
        advance(ChangesetState.OPEN, ChangesetEvent.DISMISSED)
        == ChangesetState.DISMISSED
    )


@pytest.mark.unit
def test_published_and_dismissed_are_finished():
    assert is_terminal(ChangesetState.PUBLISHED)
    assert is_terminal(ChangesetState.DISMISSED)
    assert advance(ChangesetState.PUBLISHED, ChangesetEvent.DISMISSED) is None


@pytest.mark.unit
@pytest.mark.parametrize("event", sorted(ChangesetEvent))
def test_only_an_open_changeset_accepts_any_event(event):
    """What `mark_dismissed` guards its UPDATE with. A terminal changeset accepts nothing, so
    the guard is what stops a dismissal overwriting a concurrent publish."""
    assert states_accepting(event) == (ChangesetState.OPEN.value,)


# Every (state, event) that is deliberately not an edge. A pair in neither this set nor
# `TRANSITIONS` is an oversight, and that is what the test below catches.
NOT_A_TRANSITION = {
    # Terminal both ways: publishing an already-published changeset is a no-op, not a
    # transition, and a dismissal cannot un-publish one.
    (ChangesetState.PUBLISHED, ChangesetEvent.PUBLISHED),
    (ChangesetState.PUBLISHED, ChangesetEvent.DISMISSED),
    (ChangesetState.DISMISSED, ChangesetEvent.PUBLISHED),
    (ChangesetState.DISMISSED, ChangesetEvent.DISMISSED),
}


@pytest.mark.unit
def test_every_pair_is_declared_or_denied():
    """Totality, which is what makes adding a state safe.

    Structure helps a reader; this is what stops an omission. Add a state or an event and every
    new pair has to be classified — declared as an edge or listed above as deliberately not one
    — before this passes. Silence is not an answer.
    """
    declared = {(t.frm, t.event) for t in TRANSITIONS}
    every_pair = {(s, e) for s in ChangesetState for e in ChangesetEvent}

    assert declared | NOT_A_TRANSITION == every_pair, (
        "unclassified: " + str(every_pair - declared - NOT_A_TRANSITION)
    )
    assert not (declared & NOT_A_TRANSITION), "a pair is both an edge and denied"


@pytest.mark.unit
def test_terminal_is_derived_from_the_edges_not_declared_beside_them():
    """`TERMINAL` used to be a second set naming the same fact. A state is terminal exactly
    when nothing leaves it, which the edges already say."""
    leaves = {t.frm for t in TRANSITIONS}
    assert {s for s in ChangesetState if is_terminal(s)} == set(ChangesetState) - leaves
