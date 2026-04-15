from enum import StrEnum


class PipelineRunStatus(StrEnum):
    # Workflow runner has been triggered; pipeline run has not started yet
    PENDING = "PENDING"
    # Workflow runner is actively executing
    RUNNING = "RUNNING"
    # Workflow runner finished successfully and produced output
    COMPLETED = "DONE"
    # Workflow runner encountered an unrecoverable error
    ERROR = "ERROR"
    # Error was manually acknowledged and cleared by a maintainer
    RESOLVED = "RESOLVED"
    # Pipeline run was manually cancelled (e.g. GitHub Actions run interrupted); never advanced to a terminal state
    CANCELLED = "CANCELLED"


TERMINAL_PIPELINE_RUN_STATUSES = (
    PipelineRunStatus.COMPLETED,
    PipelineRunStatus.ERROR,
    PipelineRunStatus.RESOLVED,
    PipelineRunStatus.CANCELLED,
)


class ReviewIssueStatus(StrEnum):
    PENDING = "pending"
    # A pull request has been opened to address this issue; awaiting merge
    PR_OPENED = "pr_opened"
    RESOLVED = "resolved"


class PullRequestStatus(StrEnum):
    # No PR has been created for this pipeline run yet
    DEFAULT = "DEFAULT"
    # PR exists on GitHub and is awaiting review or merge
    OPEN = "open"
    # PR was closed without merging (via UI action, webhook, or hourly sync)
    CLOSED = "closed"
    # PR was merged into the target branch
    MERGED = "merged"
