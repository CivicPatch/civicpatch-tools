"""The run lifecycle. Pure — a status in, a classification out, no mocks."""

import pytest

from core.pipeline_runs import DISMISSAL_ON_ENTERING, dismissal_for, is_final
from shared.utils.statuses import (
    DismissalReason,
    PipelineRunStatus,
    TERMINAL_PIPELINE_RUN_STATUSES,
)


@pytest.mark.unit
@pytest.mark.parametrize("status", sorted(TERMINAL_PIPELINE_RUN_STATUSES))
def test_every_terminal_status_is_final(status):
    """Parametrized over the enum rather than a hand-picked few, so a status added later has to
    be considered here instead of quietly reading as still running."""
    assert is_final(status) is True


@pytest.mark.unit
def test_a_step_report_is_not_final():
    """A running row holds a step name, not a lifecycle state — the engine reports its current
    step every loop."""
    assert is_final(PipelineRunStatus.SCRAPE_PAGE) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "status,reason",
    [
        (PipelineRunStatus.ERROR, DismissalReason.ERRORED),
        (PipelineRunStatus.CANCELLED, DismissalReason.CANCELLED),
    ],
)
def test_a_run_that_produced_nothing_dismisses_with_its_own_reason(status, reason):
    """Both settle what they minted, but they are not the same event: one gave up, someone
    stopped the other. `DismissalReason.CANCELLED` exists to say which, and the cancel endpoint
    already writes it — `dismissal_for` used to answer `errored` for both."""
    assert dismissal_for(status) is reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [PipelineRunStatus.SUCCESS, PipelineRunStatus.RESOLVED]
)
def test_a_run_that_produced_something_is_left_for_review(status):
    """Dismissing these would discard a roster nobody had looked at."""
    assert dismissal_for(status) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [PipelineRunStatus.ERROR, PipelineRunStatus.CANCELLED]
)
def test_a_run_that_produced_nothing_is_never_rejected(status):
    """A failed run is `errored`, never `rejected`: nobody read the roster and declined it.

    This used to assert `dismissal_is_legal(OPEN, reason)`, which could not fail — the
    changeset machine accepted every reason from its one unresolved state. The claim worth
    pinning is about the *run's* machine, which is where the pairing actually lives: dev holds
    a `CANCELLED` run dismissed as `rejected`, and this is what forbids minting another."""
    assert dismissal_for(status) is not DismissalReason.REJECTED


@pytest.mark.unit
def test_every_terminal_state_has_an_answer_here():
    """The table is keyed by state so a new one cannot fall into a default. That only holds if
    it covers exactly the states the graph calls terminal."""
    assert set(DISMISSAL_ON_ENTERING) == set(TERMINAL_PIPELINE_RUN_STATUSES)
