"""The changeset lifecycle. Pure — a state and an event in, a state out, no mocks."""

import pytest

from core.changeset_lifecycle import (
    INITIAL_STATE,
    TRANSITIONS,
    ChangesetEvent,
    ChangesetState,
    advance,
    dismissal_is_legal,
    is_terminal,
)
from shared.utils.statuses import ChangesetKind, DismissalReason


@pytest.mark.unit
def test_every_kind_is_born_with_something_to_show():
    """No kind waits on a run any more. A scrape's changeset is minted at ingest by a run that
    already succeeded, so it starts where an import does."""
    assert INITIAL_STATE[ChangesetKind.SCRAPE] == ChangesetState.READY
    assert INITIAL_STATE[ChangesetKind.SHEET_IMPORT] == ChangesetState.READY
    assert INITIAL_STATE[ChangesetKind.PEOPLE_EDIT] == ChangesetState.PUBLISHED


@pytest.mark.unit
def test_a_reviewable_changeset_publishes_or_is_dismissed():
    assert (
        advance(ChangesetState.READY, ChangesetEvent.PUBLISHED)
        == ChangesetState.PUBLISHED
    )
    assert (
        advance(ChangesetState.READY, ChangesetEvent.DISMISSED)
        == ChangesetState.DISMISSED
    )


@pytest.mark.unit
def test_published_and_dismissed_are_finished():
    assert is_terminal(ChangesetState.PUBLISHED)
    assert is_terminal(ChangesetState.DISMISSED)
    assert advance(ChangesetState.PUBLISHED, ChangesetEvent.DISMISSED) is None


@pytest.mark.unit
@pytest.mark.parametrize("reason", sorted(DismissalReason))
def test_every_reason_may_leave_the_one_unresolved_state(reason):
    """With one unresolved state there is nothing left to mismatch: the pairing that let a
    CANCELLED run be dismissed as `rejected` needed two states to confuse."""
    assert dismissal_is_legal(ChangesetState.READY, reason)


@pytest.mark.unit
def test_a_terminal_changeset_takes_no_reason_at_all():
    assert not dismissal_is_legal(ChangesetState.PUBLISHED, DismissalReason.REJECTED)


@pytest.mark.unit
def test_every_state_is_in_the_map():
    assert set(TRANSITIONS) == set(ChangesetState)
