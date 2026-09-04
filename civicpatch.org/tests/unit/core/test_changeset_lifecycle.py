"""The changeset lifecycle. Pure — a state and an event in, a state out, no mocks."""

import pytest

from core.changeset_lifecycle import (
    INITIAL_STATE,
    TRANSITIONS,
    ChangesetEvent,
    ChangesetState,
    advance,
    dismissal_is_legal,
    event_for_run,
    is_terminal,
)
from shared.utils.statuses import ChangesetKind, DismissalReason, PipelineRunStatus


@pytest.mark.unit
def test_a_scrape_runs_then_becomes_reviewable():
    state = INITIAL_STATE[ChangesetKind.SCRAPE]
    assert state == ChangesetState.RUNNING

    state = advance(state, ChangesetEvent.REPORTED)
    assert state == ChangesetState.RUNNING

    assert advance(state, ChangesetEvent.SUCCEEDED) == ChangesetState.READY


@pytest.mark.unit
def test_an_import_is_born_reviewable_and_an_edit_born_published():
    """Only a scrape has a run to wait for."""
    assert INITIAL_STATE[ChangesetKind.SHEET_IMPORT] == ChangesetState.READY
    assert INITIAL_STATE[ChangesetKind.PEOPLE_EDIT] == ChangesetState.PUBLISHED


@pytest.mark.unit
def test_a_failed_run_cannot_be_published():
    """The transition nothing forbids today. A run that produced no roster has nothing to
    publish, and `publish_request` would happily write an empty one."""
    assert advance(ChangesetState.FAILED, ChangesetEvent.PUBLISHED) is None


@pytest.mark.unit
def test_a_published_changeset_is_finished():
    assert is_terminal(ChangesetState.PUBLISHED)
    assert is_terminal(ChangesetState.DISMISSED)
    assert TRANSITIONS[ChangesetState.PUBLISHED] == {}


@pytest.mark.unit
def test_a_report_arriving_after_cancellation_is_not_an_error():
    """`advance` returns None rather than raising: a pipeline reporting into a run somebody
    stopped is ordinary, and the caller decides to ignore it."""
    assert advance(ChangesetState.FAILED, ChangesetEvent.REPORTED) is None


@pytest.mark.unit
def test_a_cancelled_run_cannot_be_rejected():
    """Dev holds exactly this row. A human cannot reject a roster that was never produced —
    `changesets_dismissed_reason_valid` checks the vocabulary, not the pairing."""
    assert not dismissal_is_legal(ChangesetState.FAILED, DismissalReason.REJECTED)
    assert dismissal_is_legal(ChangesetState.FAILED, DismissalReason.CANCELLED)


@pytest.mark.unit
def test_an_errored_run_cannot_be_dismissed_as_cancelled_by_a_human():
    """The other contradictory row: `ERROR` dismissed as `cancelled`. Both are machine reasons
    so both are legal from FAILED — what is not legal is a *reviewer* reason there."""
    assert not dismissal_is_legal(ChangesetState.FAILED, DismissalReason.SUPERSEDED)
    assert not dismissal_is_legal(ChangesetState.FAILED, DismissalReason.UNCHANGED)


@pytest.mark.unit
def test_a_reviewable_changeset_takes_only_reviewer_reasons():
    for reason in (
        DismissalReason.REJECTED,
        DismissalReason.SUPERSEDED,
        DismissalReason.UNCHANGED,
    ):
        assert dismissal_is_legal(ChangesetState.READY, reason)
    assert not dismissal_is_legal(ChangesetState.READY, DismissalReason.ERRORED)


@pytest.mark.unit
def test_a_step_name_is_progress_not_an_outcome():
    """`status` carries both lifecycle states and step names — `SCRAPE_PAGE` is where the run
    is, not how it ended."""
    assert event_for_run(PipelineRunStatus.SCRAPE_PAGE) == ChangesetEvent.REPORTED
    assert event_for_run(PipelineRunStatus.SUCCESS) == ChangesetEvent.SUCCEEDED
    assert event_for_run(PipelineRunStatus.ERROR) == ChangesetEvent.ERRORED


@pytest.mark.unit
def test_every_state_is_reachable_and_every_kind_starts_somewhere():
    """A state nothing leads to is a state nothing can be in."""
    reachable = {state for row in TRANSITIONS.values() for state in row.values()}
    reachable |= set(INITIAL_STATE.values())
    assert reachable == set(ChangesetState)
