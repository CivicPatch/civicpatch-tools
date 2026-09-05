"""The pipeline run lifecycle, as far as cp.org owns it.

The step order belongs to the engine, in
`pipelines/src/runners/people_collector/transitions/main.py`; cp.org owns only the end — which
reports are final, and what a final one means for the proposal the run minted.
"""

from shared.utils.statuses import (
    DismissalReason,
    PipelineRunStatus,
    TERMINAL_PIPELINE_RUN_STATUSES,
)

# Named rather than written as "not SUCCESS", so a status added later has to be considered.
ENDED_IN_FAILURE = frozenset({PipelineRunStatus.CANCELLED, PipelineRunStatus.ERROR})


def is_final(status: str) -> bool:
    """Whether this report is the last one. A run at 40% has nothing to settle."""
    return status in TERMINAL_PIPELINE_RUN_STATUSES


def dismissal_for(status: str) -> DismissalReason | None:
    """How the proposal this run minted leaves the queue, or None if it stays for review.

    `errored`, never `rejected` — the attempt gave up, nobody read the roster and declined it.
    """
    return DismissalReason.ERRORED if status in ENDED_IN_FAILURE else None
