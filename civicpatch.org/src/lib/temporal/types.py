from dataclasses import dataclass
from enum import StrEnum

# Every Temporal identifier lives here because this module imports nothing. Anything that needs
# to *name* a queue or a schedule can do so without importing the workflows or activities behind
# it — which is what keeps each worker's process small, and what stopped the API dying on the
# scrape activities' module-scope `os.environ["CIVICPATCH_ORG_URL"]`.
#
# One queue per concern, each named for what it actually carries:
JURISDICTIONS_TASK_QUEUE = "civicpatch-jurisdictions"  # inbound: open-data -> database
SINKS_TASK_QUEUE = "civicpatch-sinks"  # outbound: the sheet, open-data, parquet
EXPIRY_TASK_QUEUE = "civicpatch-expiry"  # retiring work time or a newer arrival made irrelevant
SCRAPE_TASK_QUEUE = "civicpatch-pipeline-runs"  # dispatching and polling scrape runs


class ScheduleId(StrEnum):
    OD_SYNC = "od-sync"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup"
    SWEEP_CHANGES = "sweep-changes"
    SWEEP_EVERYTHING = "sweep-everything"


class WorkflowInstanceId(StrEnum):
    OD_SYNC = "od-sync-workflow"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup-workflow"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup-workflow"
    SWEEP_CHANGES = "sweep-changes-workflow"
    SWEEP_EVERYTHING = "sweep-everything-workflow"


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
