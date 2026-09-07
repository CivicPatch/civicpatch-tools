"""The pipeline run lifecycle, as far as cp.org owns it.

The step order belongs to the engine — `PIPELINE_RUN_TRANSITIONS` in `shared/utils/statuses.py`
is the graph, and cp.org owns only the ends: which reports are final, and what a final one means
for the proposal the run minted.
"""

from shared.utils.statuses import (
    DismissalReason,
    PipelineRunStatus,
    TERMINAL_PIPELINE_RUN_STATUSES,
)

# What entering a terminal state does to what the run minted. A table rather than a branch, so
# a state added to the graph has to be given an answer here instead of falling into a default.
#
# `errored`, never `rejected` — the attempt gave up, nobody read the roster and declined it.
DISMISSAL_ON_ENTERING: dict[str, DismissalReason | None] = {
    # Produced a roster. It stays for review.
    PipelineRunStatus.SUCCESS: None,
    PipelineRunStatus.RESOLVED: None,
    PipelineRunStatus.ERROR: DismissalReason.ERRORED,
    # Its own reason, not `errored`: somebody stopped this one on purpose, and
    # `DismissalReason.CANCELLED` exists to say so.
    PipelineRunStatus.CANCELLED: DismissalReason.CANCELLED,
}


def is_final(status: str) -> bool:
    """Whether this report is the last one. A run at 40% has nothing to settle."""
    return status in TERMINAL_PIPELINE_RUN_STATUSES


def dismissal_for(status: str) -> DismissalReason | None:
    """How the proposal this run minted leaves the queue, or None if it stays for review."""
    return DISMISSAL_ON_ENTERING.get(status)
