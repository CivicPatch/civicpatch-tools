from runners.engine import Transitions
from shared.utils.statuses import PipelineRunStatus
from runners.pipeline01_governing_law_collector.schemas import GoverningLawCollectorStep

# A governing_law_collector run's whole life. civicpatch.org owns the two ends before INIT.
GOVERNING_LAW_COLLECTOR_TRANSITIONS: Transitions = {
    PipelineRunStatus.PENDING: frozenset({PipelineRunStatus.RUNNING}),
    PipelineRunStatus.RUNNING: frozenset({PipelineRunStatus.INIT}),
    PipelineRunStatus.INIT: frozenset({GoverningLawCollectorStep.FIND_SOURCE}),
    GoverningLawCollectorStep.FIND_SOURCE: frozenset({
        GoverningLawCollectorStep.FETCH_SOURCE,
        # Nothing to fetch: no charter and no general law on record.
        GoverningLawCollectorStep.WRITE_GOVERNING_LAW,
    }),
    GoverningLawCollectorStep.FETCH_SOURCE: frozenset({
        GoverningLawCollectorStep.PREPROCESS_PAGE_CONTENT,
        # The host refused this url; on to the next, or done.
        GoverningLawCollectorStep.FETCH_SOURCE,
        GoverningLawCollectorStep.WRITE_GOVERNING_LAW,
    }),
    GoverningLawCollectorStep.PREPROCESS_PAGE_CONTENT: frozenset({
        GoverningLawCollectorStep.STORE_SOURCE_PAGE,
        # Thin by plain GET: the same url again, by browser. Thin even then: the next url.
        GoverningLawCollectorStep.FETCH_SOURCE,
        GoverningLawCollectorStep.WRITE_GOVERNING_LAW,
    }),
    GoverningLawCollectorStep.STORE_SOURCE_PAGE: frozenset({
        GoverningLawCollectorStep.FETCH_SOURCE,
        GoverningLawCollectorStep.WRITE_GOVERNING_LAW,
    }),
    GoverningLawCollectorStep.WRITE_GOVERNING_LAW: frozenset({PipelineRunStatus.SUCCESS}),
    PipelineRunStatus.SEND_ERROR: frozenset({PipelineRunStatus.ERROR}),
    PipelineRunStatus.SUCCESS: frozenset(),
    PipelineRunStatus.ERROR: frozenset(),
    PipelineRunStatus.CANCELLED: frozenset(),
    PipelineRunStatus.RESOLVED: frozenset(),
}
