from runners.engine import Transitions
from shared.utils.statuses import PipelineRunStatus

# A people collector run's whole life. The engine walks the middle, civicpatch.org owns the ends.
PEOPLE_COLLECTOR_TRANSITIONS: Transitions = {
    # civicpatch.org's, before the engine exists
    PipelineRunStatus.PENDING: frozenset({PipelineRunStatus.RUNNING}),
    PipelineRunStatus.RUNNING: frozenset({PipelineRunStatus.INIT}),
    # the engine's
    PipelineRunStatus.INIT: frozenset({PipelineRunStatus.RESEARCH_MUNICIPALITY}),
    PipelineRunStatus.RESEARCH_MUNICIPALITY: frozenset({PipelineRunStatus.SCRAPE_PAGE}),
    PipelineRunStatus.SCRAPE_PAGE: frozenset({
        PipelineRunStatus.PREPROCESS_PAGE_CONTENT,
        PipelineRunStatus.SCRAPE_PAGE,
        PipelineRunStatus.CLEANUP,
        PipelineRunStatus.FIND_JURISDICTION_URL,
    }),
    PipelineRunStatus.PREPROCESS_PAGE_CONTENT: frozenset({
        PipelineRunStatus.PROCESS_PAGE_CONTENT,
        PipelineRunStatus.SCRAPE_PAGE,
        PipelineRunStatus.FIND_JURISDICTION_URL,
    }),
    PipelineRunStatus.PROCESS_PAGE_CONTENT: frozenset({
        PipelineRunStatus.CLEANUP,
        PipelineRunStatus.SCRAPE_PAGE,
    }),
    PipelineRunStatus.CLEANUP: frozenset({PipelineRunStatus.REVIEW_OUTPUT}),
    PipelineRunStatus.REVIEW_OUTPUT: frozenset({
        PipelineRunStatus.SAVE_OUTPUT,
        PipelineRunStatus.FIND_JURISDICTION_URL,
    }),
    PipelineRunStatus.FIND_JURISDICTION_URL: frozenset({
        PipelineRunStatus.REVIEW_OUTPUT,
        PipelineRunStatus.SCRAPE_PAGE,
    }),
    PipelineRunStatus.SAVE_OUTPUT: frozenset({PipelineRunStatus.SEND_SUCCESS}),
    PipelineRunStatus.SEND_SUCCESS: frozenset({PipelineRunStatus.SUCCESS}),
    PipelineRunStatus.SEND_ERROR: frozenset({PipelineRunStatus.ERROR}),
    # nothing follows these
    PipelineRunStatus.SUCCESS: frozenset(),
    PipelineRunStatus.ERROR: frozenset(),
    PipelineRunStatus.CANCELLED: frozenset(),
    PipelineRunStatus.RESOLVED: frozenset(),
}
