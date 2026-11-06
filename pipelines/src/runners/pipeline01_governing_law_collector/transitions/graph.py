from runners.engine import Transitions
from shared.utils.statuses import PipelineRunStatus
from ..schemas import GoverningLawCollectorStep

# A governing_law_collector run's whole life. civicpatch.org owns the two ends before INIT.
GOVERNING_LAW_COLLECTOR_TRANSITIONS: Transitions = {
    PipelineRunStatus.PENDING: frozenset({PipelineRunStatus.RUNNING}),
    PipelineRunStatus.RUNNING: frozenset({PipelineRunStatus.INIT}),
    PipelineRunStatus.INIT: frozenset({GoverningLawCollectorStep.FIND_SOURCES}),
    GoverningLawCollectorStep.FIND_SOURCES: frozenset({GoverningLawCollectorStep.STORE_SOURCES}),
    GoverningLawCollectorStep.STORE_SOURCES: frozenset({GoverningLawCollectorStep.WRITE_GOVERNING_LAW}),
    GoverningLawCollectorStep.WRITE_GOVERNING_LAW: frozenset({PipelineRunStatus.SUCCESS}),
    PipelineRunStatus.SEND_ERROR: frozenset({PipelineRunStatus.ERROR}),
    PipelineRunStatus.SUCCESS: frozenset(),
    PipelineRunStatus.ERROR: frozenset(),
    PipelineRunStatus.CANCELLED: frozenset(),
    PipelineRunStatus.RESOLVED: frozenset(),
}
