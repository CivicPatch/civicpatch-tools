from dataclasses import dataclass
from enum import StrEnum

# Every Temporal identifier lives here because this module imports nothing. Anything that needs
# to *name* a queue or a schedule can do so without importing the workflows or activities behind
# it — which is what keeps each worker's process small, and what stopped the API dying on the
# scrape activities' module-scope `os.environ["CIVICPATCH_ORG_URL"]`.
#
# One queue per concern, each named for what it actually carries:
SOURCE_TASK_QUEUE = "civicpatch-source"  # inbound: open-data -> database
SINKS_TASK_QUEUE = "civicpatch-sinks"  # outbound: the sheet, open-data, parquet
CLEANUP_TASK_QUEUE = "civicpatch-cleanup"  # retiring work time or a newer arrival made irrelevant
PIPELINE_RUNS_TASK_QUEUE = "civicpatch-pipeline-runs"  # dispatching and polling scrape runs

# The whitelist. Running work on any other queue is work whose worker is gone: nothing polls it,
# and `terminate_undeclared_workflows` is scoped per queue, so nothing sweeps it either. Dropping
# a queue from here is how you retire it — see `terminate_workflows_on_undeclared_queues`.
TASK_QUEUES = frozenset(
    {
        SOURCE_TASK_QUEUE,
        SINKS_TASK_QUEUE,
        CLEANUP_TASK_QUEUE,
        PIPELINE_RUNS_TASK_QUEUE,
    }
)


# Every member below is the SCREAMING_SNAKE of its own value. Say what a thing is once: a member
# whose name drifts from its value is a second, silent claim about what the id means.
#
# Schedule ids are kebab throughout, workflow ids colon-separated, so the two never collide —
# Temporal shows both and confuses them in its own UI when they match.
class ScheduleId(StrEnum):
    SOURCE_OPEN_DATA_JURISDICTIONS = "source-open-data-jurisdictions"
    CLEANUP_PIPELINE_RUNS = "cleanup-pipeline-runs"
    CLEANUP_REVIEW_SESSIONS = "cleanup-review-sessions"
    SINK_WRITE_RECENT_CHANGES = "sink-write-recent-changes"
    SINK_WRITE_EVERYTHING = "sink-write-everything"
    SINK_WRITE_ACTIVITY_FEED = "sink-write-activity-feed"


# `source:` and `sink:` are the direction, so no verb has to carry it. Depth then carries scope:
# `sink:<name>:...` is one sink's own work, `sink:<verb>` fans out across all of them. open-data
# appears under both because it is both — read for jurisdictions, written for rosters.
class WorkflowInstanceId(StrEnum):
    SOURCE_OPEN_DATA_JURISDICTIONS = "source:open-data:jurisdictions"
    CLEANUP_PIPELINE_RUNS = "cleanup:pipeline-runs"
    CLEANUP_REVIEW_SESSIONS = "cleanup:review-sessions"
    SINK_WRITE_RECENT_CHANGES = "sink:write-recent-changes"
    SINK_WRITE_EVERYTHING = "sink:write-everything"
    SINK_WRITE_ACTIVITY_FEED = "sink:write-activity-feed"
    SINK_DISPATCH_ACTIVITY_FEED = "sink:dispatch-activity-feed"


@dataclass
class OpenDataCommitItem:
    """One jurisdiction inside a batch commit."""

    file_path: str
    # Every changeset this file's content lands, each stamped with the commit url. Plural for
    # the sweep covers a window of change rather than one publish.
    changeset_ids: list[str]
    jurisdiction_ocdid: str


@dataclass
class OpenDataBatchCommitRequest:
    batch_id: str
    items: list[OpenDataCommitItem]
    commit_message: str


class RunConclusion(StrEnum):
    """How a scrape ended, as `poll_pipeline_run_status` reports it to the workflow.

    Here rather than beside the workflows: both the workflows and the activities need it, and
    workflows already import activities, so the other direction would be a cycle.
    """

    SUCCESS = "success"
    FAILURE = "failure"
