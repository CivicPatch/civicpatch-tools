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
    SEARCH_LINKS = "SEARCH_LINKS"
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


TERMINAL_PIPELINE_RUN_STATUSES = (
    PipelineRunStatus.SUCCESS,
    PipelineRunStatus.ERROR,
    PipelineRunStatus.RESOLVED,
    PipelineRunStatus.CANCELLED,
)


class ReviewIssueStatus(StrEnum):
    PENDING = "pending"
    # A pull request has been opened to address this issue; awaiting merge
    PR_OPENED = "pr_opened"
    RESOLVED = "resolved"


class PipelineRunErrorType(StrEnum):
    # pipeline_error is the server-side fallback; the pipeline never sets it explicitly
    NO_INFO = "no_info"


class PipelineIssueType(StrEnum):
    UNRECOGNIZED_ROLE = "unrecognized_role"
    DOMAIN_REDIRECTED = "domain_redirected"


class PullRequestStatus(StrEnum):
    # No PR has been created for this pipeline run yet
    DEFAULT = "DEFAULT"
    # PR exists on GitHub and is awaiting review or merge
    OPEN = "open"
    # PR was closed without merging (via UI action, webhook, or hourly sync)
    CLOSED = "closed"
    # PR was merged into the target branch
    MERGED = "merged"
