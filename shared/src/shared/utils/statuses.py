from enum import StrEnum


class JobStatus(StrEnum):
    # Workflow runner has been triggered; job has not started yet
    PENDING = "PENDING"
    # Workflow runner is actively executing
    RUNNING = "RUNNING"
    # Workflow runner finished successfully and produced output
    COMPLETED = "DONE"
    # Workflow runner encountered an unrecoverable error
    ERROR = "ERROR"
    # Error was manually acknowledged and cleared by a maintainer
    RESOLVED = "RESOLVED"
    # Job was manually cancelled (e.g. GitHub Actions run interrupted); never advanced to a terminal state
    CANCELLED = "CANCELLED"


TERMINAL_JOB_STATUSES = (
    JobStatus.COMPLETED,
    JobStatus.ERROR,
    JobStatus.RESOLVED,
    JobStatus.CANCELLED,
)


class ReviewIssueStatus(StrEnum):
    PENDING = "pending"
    # A pull request has been opened to address this issue; awaiting merge
    PR_OPENED = "pr_opened"
    RESOLVED = "resolved"


class PullRequestStatus(StrEnum):
    # No PR has been created for this job yet
    DEFAULT = "DEFAULT"
    # PR exists on GitHub and is awaiting review or merge
    OPEN = "open"
    # PR was closed without merging (via UI action, webhook, or hourly sync)
    CLOSED = "closed"
    # PR was merged into the target branch
    MERGED = "merged"
