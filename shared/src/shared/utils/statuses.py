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
    RESOLVED = "resolved"
    # Automatically set on all pending issues when a newer run for the same jurisdiction reaches a terminal state
    SUPERSEDED = "superseded"


TERMINAL_PIPELINE_ISSUE_STATUSES = (
    PipelineIssueStatus.RESOLVED,
    PipelineIssueStatus.SUPERSEDED,
)


class PipelineRunErrorType(StrEnum):
    # pipeline_error is the server-side fallback; the pipeline never sets it explicitly
    #
    # Not a fault in the source, unlike its two neighbours: the domain resolved and the pages
    # read, there was simply no roster to find. It reads on a jurisdiction's timeline as an
    # outcome a maintainer can act on, not as the pipeline breaking.
    NO_ROSTER_FOUND = "no_roster_found"
    DOMAIN_INACTIVE = "domain_inactive"
    # Domain resolved but navigation failed (timeout, DNS failure, HTTP error, etc.)
    DOMAIN_NAVIGATION_ERROR = "domain_navigation_error"


class PipelineIssueType(StrEnum):
    # A queued merge failed; the PR stays parked (merge_enqueued_at kept) out of the review
    # pool until an admin dismisses this issue, which clears the park.
    MERGE_FAILED = "merge_failed"
    # Generic pipeline failure (run errored, or timed out and was expired) — the default
    # issue type when a run has no more specific error_step.
    PIPELINE_ERROR = "pipeline_error"
    # Filed manually by a reviewer from the review page (not pipeline-detected), but follows
    # the identical issues lifecycle above, including scrape-candidate exclusion while pending.
    USER_REPORTED = "user_reported"
    # The run stopped at its spend ceiling before it had the roster it was looking for, so the
    # proposal is partial. Deliberately NOT in `PipelineRunErrorType`: the run succeeded and
    # minted a changeset, and this hangs off that changeset because the reviewer reading the
    # roster is who needs to know it is short. Without it the cap was invisible outside the
    # container log — a capped run and a jurisdiction with no officials looked identical.
    COST_CAP_REACHED = "cost_cap_reached"
    # The crawl finished but found fewer people than the roster we hold (or than research
    # named) led it to expect. Short by more than the crawler's own tolerance, so a run that
    # stopped because it had enough never files this.
    FEWER_THAN_EXPECTED = "fewer_than_expected"


# Issue types a run can produce, as opposed to ones about a proposal. These are keyed on the
# run rather than a changeset, because a run that fails mints no changeset — so the issues page
# renders the key bare. Defined once: it is both what cp.org accepts from the pipeline and what
# the issues endpoint treats as run-shaped, and those two drifting is how a raw exception string
# became an issue type.
RUN_LEVEL_ISSUE_TYPES = frozenset(PipelineRunErrorType) | {
    PipelineIssueType.PIPELINE_ERROR
}


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


COLLECTION_KINDS = (ChangesetKind.SCRAPE, ChangesetKind.SHEET_IMPORT)


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
