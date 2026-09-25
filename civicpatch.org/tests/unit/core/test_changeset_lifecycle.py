"""What varies by changeset kind, and which states an event may leave. Pure, no mocks.

`advance` and `is_terminal` went on 2026-09-25 with their three tests: neither had a production
caller. Every fact those tests asserted --- open publishes or is dismissed, and published and
dismissed are finished --- is still pinned, by `test_every_pair_is_declared_or_denied` classifying
every (state, event) pair and by `test_only_an_open_changeset_accepts_any_event`.
"""

import pytest

from core.changeset_lifecycle import (
    INITIAL_STATE,
    TRANSITIONS,
    ChangesetEvent,
    ChangesetState,
    states_accepting,
)
from shared.utils.statuses import ChangesetKind


@pytest.mark.unit
def test_every_kind_is_born_where_the_table_says():
    """This verified three kinds' birth states. It now verifies all five, because a kind missing
    from `INITIAL_STATE` was invisible to it --- `rollback` and `jurisdiction_edit` were both
    absent --- and rollback moved to born-open on 2026-09-25, which is the change most worth
    catching if it ever moved back."""
    assert INITIAL_STATE == {
        ChangesetKind.SCRAPE: ChangesetState.OPEN,
        ChangesetKind.SHEET_IMPORT: ChangesetState.OPEN,
        ChangesetKind.PEOPLE_EDIT: ChangesetState.PUBLISHED,
        ChangesetKind.JURISDICTION_EDIT: ChangesetState.PUBLISHED,
        ChangesetKind.ROLLBACK: ChangesetState.OPEN,
    }
    assert set(INITIAL_STATE) == set(ChangesetKind), "every kind has a birth state"


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
