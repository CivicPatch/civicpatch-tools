from runners.engine import Transitions
from ..schemas import OrganizationsCollectorStep
from shared.utils.statuses import PipelineRunStatus

# An organizations_collector run's whole life. civicpatch.org owns the two ends before INIT.
ORGANIZATIONS_COLLECTOR_TRANSITIONS: Transitions = {
    PipelineRunStatus.PENDING: frozenset({PipelineRunStatus.RUNNING}),
    PipelineRunStatus.RUNNING: frozenset({PipelineRunStatus.INIT}),
    PipelineRunStatus.INIT: frozenset({OrganizationsCollectorStep.SELECT_SECTIONS}),
    OrganizationsCollectorStep.SELECT_SECTIONS: frozenset({
        OrganizationsCollectorStep.EXTRACT,
        # No cached text to read: plan 1 found no law, or has not run.
        OrganizationsCollectorStep.WRITE,
    }),
    OrganizationsCollectorStep.EXTRACT: frozenset({OrganizationsCollectorStep.VERIFY}),
    OrganizationsCollectorStep.VERIFY: frozenset({
        OrganizationsCollectorStep.WRITE,
        # Claims that failed every rung are asked again, the verified ones kept.
        OrganizationsCollectorStep.EXTRACT,
    }),
    OrganizationsCollectorStep.WRITE: frozenset({PipelineRunStatus.SUCCESS}),
    PipelineRunStatus.SEND_ERROR: frozenset({PipelineRunStatus.ERROR}),
    PipelineRunStatus.SUCCESS: frozenset(),
    PipelineRunStatus.ERROR: frozenset(),
    PipelineRunStatus.CANCELLED: frozenset(),
    PipelineRunStatus.RESOLVED: frozenset(),
}
