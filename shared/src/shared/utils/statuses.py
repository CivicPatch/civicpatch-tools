from enum import StrEnum


class JobStatus(StrEnum):
    # Workflow runner has been triggered; job has not started yet
    PENDING = "PENDING"
    # Workflow runner finished successfully and produced output
    COMPLETED = "COMPLETED"
    # Workflow runner encountered an unrecoverable error
    ERROR = "ERROR"
    # Error was manually acknowledged and cleared by a maintainer
    RESOLVED = "RESOLVED"
    # Pipeline exited mid-run awaiting human review; resumes on human_approval signal
    PAUSED = "PAUSED"


class PullRequestStatus(StrEnum):
    # No PR has been created for this job yet
    DEFAULT = "DEFAULT"
    # PR exists on GitHub and is awaiting review or merge
    OPEN = "open"
    # PR was closed without merging (via UI action, webhook, or hourly sync)
    CLOSED = "closed"
    # PR was merged into the target branch
    MERGED = "merged"


# TODO: Drop RequestStatus and the requests.status column.
# The full request lifecycle is already derivable from jobs.status (pipeline phase)
# and pull_requests.status (review/PR phase) via their FK relationships.
# This enum and column are written once at creation and never updated — they add
# maintenance burden without providing information that isn't already in the joins.
class RequestStatus(StrEnum):
    DEFAULT = "DEFAULT"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
