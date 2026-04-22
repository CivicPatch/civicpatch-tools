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
    MERGE_RECORDS_ACROSS_LLMS = "MERGE_RECORDS_ACROSS_LLMS"
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
    # Automatically set on error-category issues when a newer run for the same jurisdiction reaches a terminal state
    SUPERSEDED = "superseded"


TERMINAL_PIPELINE_ISSUE_STATUSES = (PipelineIssueStatus.RESOLVED, PipelineIssueStatus.SUPERSEDED)


class PipelineRunErrorType(StrEnum):
    # pipeline_error is the server-side fallback; the pipeline never sets it explicitly
    NO_INFO = "no_info"
    DOMAIN_INACTIVE = "domain_inactive"
    # Domain resolves and server exists but didn't respond within the timeout
    DOMAIN_NAVIGATION_TIMEOUT = "domain_navigation_timeout"


class PipelineIssueCategory(StrEnum):
    ERROR = "error"
    ISSUE = "issue"


class PipelineIssueType(StrEnum):
    UNRECOGNIZED_ROLE = "unrecognized_role"
    DOMAIN_REDIRECTED = "domain_redirected"
    DOMAIN_INACTIVE_FIXED = "domain_inactive_fixed"


class PullRequestStatus(StrEnum):
    # No PR has been created for this pipeline run yet
    DEFAULT = "DEFAULT"
    # PR exists on GitHub and is awaiting review or merge
    OPEN = "open"
    # PR was closed without merging (via UI action, webhook, or hourly sync)
    CLOSED = "closed"
    # PR was merged into the target branch
    MERGED = "merged"
