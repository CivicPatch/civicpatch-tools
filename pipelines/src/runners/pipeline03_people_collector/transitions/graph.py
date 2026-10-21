from runners.engine import Transitions
from shared.utils.statuses import PipelineRunStatus
from ..schemas import PeopleCollectorStep

# A people collector run's whole life. The engine walks the middle, civicpatch.org owns the ends.
PEOPLE_COLLECTOR_TRANSITIONS: Transitions = {
    # civicpatch.org's, before the engine exists
    PipelineRunStatus.PENDING: frozenset({PipelineRunStatus.RUNNING}),
    PipelineRunStatus.RUNNING: frozenset({PipelineRunStatus.INIT}),
    # the engine's
    PipelineRunStatus.INIT: frozenset({PeopleCollectorStep.RESEARCH_MUNICIPALITY}),
    PeopleCollectorStep.RESEARCH_MUNICIPALITY: frozenset({PeopleCollectorStep.SCRAPE_PAGE}),
    PeopleCollectorStep.SCRAPE_PAGE: frozenset({
        PeopleCollectorStep.PREPROCESS_PAGE_CONTENT,
        PeopleCollectorStep.SCRAPE_PAGE,
        PeopleCollectorStep.CLEANUP,
        PeopleCollectorStep.FIND_JURISDICTION_URL,
    }),
    PeopleCollectorStep.PREPROCESS_PAGE_CONTENT: frozenset({
        PeopleCollectorStep.PROCESS_PAGE_CONTENT,
        PeopleCollectorStep.SCRAPE_PAGE,
        PeopleCollectorStep.FIND_JURISDICTION_URL,
    }),
    PeopleCollectorStep.PROCESS_PAGE_CONTENT: frozenset({
        PeopleCollectorStep.CLEANUP,
        PeopleCollectorStep.SCRAPE_PAGE,
    }),
    PeopleCollectorStep.CLEANUP: frozenset({PeopleCollectorStep.REVIEW_OUTPUT}),
    PeopleCollectorStep.REVIEW_OUTPUT: frozenset({
        PeopleCollectorStep.SAVE_OUTPUT,
        PeopleCollectorStep.FIND_JURISDICTION_URL,
    }),
    PeopleCollectorStep.FIND_JURISDICTION_URL: frozenset({
        PeopleCollectorStep.REVIEW_OUTPUT,
        PeopleCollectorStep.SCRAPE_PAGE,
    }),
    PeopleCollectorStep.SAVE_OUTPUT: frozenset({PeopleCollectorStep.SEND_SUCCESS}),
    PeopleCollectorStep.SEND_SUCCESS: frozenset({PipelineRunStatus.SUCCESS}),
    PipelineRunStatus.SEND_ERROR: frozenset({PipelineRunStatus.ERROR}),
    # nothing follows these
    PipelineRunStatus.SUCCESS: frozenset(),
    PipelineRunStatus.ERROR: frozenset(),
    PipelineRunStatus.CANCELLED: frozenset(),
    PipelineRunStatus.RESOLVED: frozenset(),
}
