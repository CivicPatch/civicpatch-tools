from enum import StrEnum


class PipelineRunStatus(StrEnum):
    # Lifecycle states
    PENDING = "PENDING"
    # ⚠️ Written once, by the worker's first activity, and overwritten by the engine's first
    # step report seconds later — so it is real but never observed in a stored row, and two
    # separate sweeps have called it dead. Only `typecheck-worker` catches that; `worker/` has
    # no tests. Nothing branches on it: every reader asks whether the status is terminal.
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


class RequestReviewStatus(StrEnum):
    """Where a request sits in the review lifecycle, derived from `published_at`/`dismissed_at`.

    Publishing is a database write, so there is no `open`/`merged` distinction to make — a
    request is awaiting review, published, or dismissed. Derived rather than stored: the two
    timestamps are the state, and a CHECK already forbids both being set.
    """

    PENDING = "pending"
    PUBLISHED = "published"
    DISMISSED = "dismissed"


class ChangesetKind(StrEnum):
    """Which producer made this changeset. The discriminator, mandatory and exact.

    It used to say which domain object the row was *about* (`people`), which left three
    producers sharing one value and told apart by a conjunction of `status IS NULL` and
    `batch_id IS NOT NULL` — neither of which is about provenance.

    Only SCRAPE has a pipeline run behind it, and a CHECK enforces that both ways.
    JURISDICTION_EDIT is kept out of the review pool: it edits a registry civicpatch does
    not own, so there is nothing here to review.
    """

    SCRAPE = "scrape"
    SHEET_IMPORT = "sheet_import"
    PEOPLE_EDIT = "people_edit"
    JURISDICTION_EDIT = "jurisdiction_edit"


# Kinds that went and read a source. A publish that read one may say "still listed"; a hand
# edit may not, and "ok / failed" is a collection attempt's vocabulary, not an edit's.
SOURCE_READING_KINDS = (ChangesetKind.SCRAPE, ChangesetKind.SHEET_IMPORT)


class DismissalReason(StrEnum):
    REJECTED = "rejected"  # a reviewer read the roster and said no
    CANCELLED = "cancelled"  # somebody stopped the run before it produced one
    ERRORED = "errored"  # the run ended without a roster; nobody decided
    SUPERSEDED = "superseded"  # a newer roster for this jurisdiction won


class ChangeLogType(StrEnum):
    PUBLISH_REVIEW = "publish_review"
    DISMISS_REVIEW = "dismiss_review"
    ADD_PERSON = "add_person"
    EDIT_PERSON = "edit_person"
    DELETE_PERSON = "delete_person"
    EDIT_JURISDICTION = "edit_jurisdiction"
    # Role taxonomy. Kind (canonical|exclusion) lives in the payload, not the
    # type. Alias deltas fold into edit_role's payload as aliases_added/removed.
    # Seats. The jurisdiction is a real column here, unlike roles, which are global.
    ADD_POST = "add_post"
    EDIT_POST = "edit_post"
    DELETE_POST = "delete_post"
    # Seat and move are one type; `moved_from` in the payload tells them apart.
    ASSIGN_MEMBERSHIP = "assign_membership"
    # A human asserting a field value directly, rather than by editing a row. The only path
    # that carries `sources` — "phoned the clerk" exists nowhere else.
    ASSERT_FIELD = "assert_field"
    ADD_ROLE = "add_role"
    EDIT_ROLE = "edit_role"
    DELETE_ROLE = "delete_role"
    REORDER_ROLES = "reorder_roles"
