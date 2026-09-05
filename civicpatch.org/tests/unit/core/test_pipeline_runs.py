"""The run lifecycle. Pure — a status in, a classification out, no mocks."""

import pytest

from core.pipeline_runs import ENDED_IN_FAILURE, dismissal_for, is_final
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
@pytest.mark.parametrize("status", sorted(ENDED_IN_FAILURE))
def test_a_run_that_failed_dismisses_what_it_minted(status):
    assert dismissal_for(status) is DismissalReason.ERRORED


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [PipelineRunStatus.SUCCESS, PipelineRunStatus.RESOLVED]
)
def test_a_run_that_produced_something_is_left_for_review(status):
    """Dismissing these would discard a roster nobody had looked at."""
    assert dismissal_for(status) is None


@pytest.mark.unit
@pytest.mark.parametrize("status", sorted(ENDED_IN_FAILURE))
def test_the_two_lifecycles_agree_on_the_reason(status):
    """A failed run is `errored`, never `rejected`: nobody read the roster and declined it.

    This used to assert `dismissal_is_legal(OPEN, reason)`, which could not fail — the
    changeset machine accepted every reason from its one unresolved state. The claim worth
    pinning is about the *run's* machine, which is where the pairing actually lives: dev holds
    a `CANCELLED` run dismissed as `rejected`, and this is what forbids minting another."""
    assert dismissal_for(status) is DismissalReason.ERRORED
