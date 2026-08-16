from enum import StrEnum


class PipelineRunStatus(StrEnum):
    # Lifecycle states
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"
    # Step-level progress states
    INIT = "INIT"
    RESEARCH_MUNICIPALITY = "RESEARCH_MUNICIPALITY"
    SCRAPE_PAGE = "SCRAPE_PAGE"
    PREPROCESS_PAGE_CONTENT = "PREPROCESS_PAGE_CONTENT"
    PROCESS_PAGE_CONTENT = "PROCESS_PAGE_CONTENT"
    MERGE_RECORDS_WITHIN_LLM = "MERGE_RECORDS_WITHIN_LLM"
    FORMAT_OUTPUT = "FORMAT_OUTPUT"
    CLEANUP = "CLEANUP"
    REVIEW_OUTPUT = "REVIEW_OUTPUT"
    SAVE_OUTPUT = "SAVE_OUTPUT"
    SEND_SUCCESS = "SEND_SUCCESS"
    SEND_ERROR = "SEND_ERROR"
    RETRY = "RETRY"
    FIND_JURISDICTION_URL = "FIND_JURISDICTION_URL"


TERMINAL_PIPELINE_RUN_STATUSES = (
    PipelineRunStatus.SUCCESS,
    PipelineRunStatus.ERROR,
    PipelineRunStatus.RESOLVED,
    PipelineRunStatus.CANCELLED,
)


class PipelineIssueStatus(StrEnum):
    PENDING = "pending"
    # A pull request has been opened to address this issue; awaiting merge
    PR_OPENED = "pr_opened"
    RESOLVED = "resolved"
    # Automatically set on all pending issues when a newer run for the same jurisdiction reaches a terminal state
    SUPERSEDED = "superseded"


TERMINAL_PIPELINE_ISSUE_STATUSES = (
    PipelineIssueStatus.RESOLVED,
    PipelineIssueStatus.SUPERSEDED,
)


class PipelineRunErrorType(StrEnum):
    # pipeline_error is the server-side fallback; the pipeline never sets it explicitly
    NO_INFO = "no_info"
    DOMAIN_INACTIVE = "domain_inactive"
    # Domain resolved but navigation failed (timeout, DNS failure, HTTP error, etc.)
    DOMAIN_NAVIGATION_ERROR = "domain_navigation_error"


class PipelineIssueType(StrEnum):
    # TBD remove: the pipeline stopped emitting these 2026-08-16 — `parse_label` recovers
    # `unmatched` from the raw label instead. Kept until the existing rows are drained.
    UNRECOGNIZED_ROLE = "unrecognized_role"
    # A queued merge failed; the PR stays parked (merge_enqueued_at kept) out of the review
    # pool until an admin dismisses this issue, which clears the park.
    MERGE_FAILED = "merge_failed"
    # Generic pipeline failure (run errored, or timed out and was expired) — the default
    # issue type when a run has no more specific error_step.
    PIPELINE_ERROR = "pipeline_error"
    # Filed manually by a reviewer from the review page (not pipeline-detected), but follows
    # the identical issues lifecycle above, including scrape-candidate exclusion while pending.
    USER_REPORTED = "user_reported"


class PullRequestStatus(StrEnum):
    # No PR has been created for this pipeline run yet
    DEFAULT = "DEFAULT"
    # PR exists on GitHub and is awaiting review or merge
    OPEN = "open"
    # PR was closed without merging (via UI action, webhook, or hourly sync)
    CLOSED = "closed"
    # PR was merged into the target branch
    MERGED = "merged"


class RequestType(StrEnum):
    """What a request asked the system to do.

    Only PEOPLE has a pipeline run behind it. JURISDICTION_MANUAL_EDIT exists so a
    hand-edited jurisdiction field gets a tracked PR like any other change, and must
    be kept out of the review pool — there is nothing in it to review.
    """

    PEOPLE = "people"
    JURISDICTION_MANUAL_EDIT = "jurisdiction_manual_edit"


class ChangeLogType(StrEnum):
    MERGE_REVIEW = "merge_review"
    CLOSE_REVIEW = "close_review"
    ADD_PERSON = "add_person"
    EDIT_PERSON = "edit_person"
    DELETE_PERSON = "delete_person"
    EDIT_JURISDICTION = "edit_jurisdiction"
    # Role taxonomy. Kind (canonical|exclusion) lives in the payload, not the
    # type. Alias deltas fold into edit_role's payload as aliases_added/removed.
    ADD_ROLE = "add_role"
    EDIT_ROLE = "edit_role"
    DELETE_ROLE = "delete_role"
    REORDER_ROLES = "reorder_roles"
