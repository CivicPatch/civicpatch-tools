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
    FIND_JURISDICTION_URL = "FIND_JURISDICTION_URL"


# A run's whole life. The engine walks the middle, civicpatch.org owns the ends, and both read
# this — they used to disagree about which states were terminal.
PIPELINE_RUN_TRANSITIONS: dict[PipelineRunStatus, frozenset[PipelineRunStatus]] = {
    # civicpatch.org's, before the engine exists
    PipelineRunStatus.PENDING: frozenset({PipelineRunStatus.RUNNING}),
    PipelineRunStatus.RUNNING: frozenset({PipelineRunStatus.INIT}),
    # the engine's
    PipelineRunStatus.INIT: frozenset({PipelineRunStatus.RESEARCH_MUNICIPALITY}),
    PipelineRunStatus.RESEARCH_MUNICIPALITY: frozenset({PipelineRunStatus.SCRAPE_PAGE}),
    PipelineRunStatus.SCRAPE_PAGE: frozenset({
        PipelineRunStatus.PREPROCESS_PAGE_CONTENT,
        PipelineRunStatus.SCRAPE_PAGE,
        PipelineRunStatus.CLEANUP,
        PipelineRunStatus.FIND_JURISDICTION_URL,
    }),
    PipelineRunStatus.PREPROCESS_PAGE_CONTENT: frozenset({
        PipelineRunStatus.PROCESS_PAGE_CONTENT,
        PipelineRunStatus.SCRAPE_PAGE,
        PipelineRunStatus.FIND_JURISDICTION_URL,
    }),
    PipelineRunStatus.PROCESS_PAGE_CONTENT: frozenset({
        PipelineRunStatus.CLEANUP,
        PipelineRunStatus.SCRAPE_PAGE,
    }),
    PipelineRunStatus.CLEANUP: frozenset({PipelineRunStatus.REVIEW_OUTPUT}),
    PipelineRunStatus.REVIEW_OUTPUT: frozenset({
        PipelineRunStatus.SAVE_OUTPUT,
        PipelineRunStatus.FIND_JURISDICTION_URL,
    }),
    PipelineRunStatus.FIND_JURISDICTION_URL: frozenset({
        PipelineRunStatus.REVIEW_OUTPUT,
        PipelineRunStatus.SCRAPE_PAGE,
    }),
    PipelineRunStatus.SAVE_OUTPUT: frozenset({PipelineRunStatus.SEND_SUCCESS}),
    PipelineRunStatus.SEND_SUCCESS: frozenset({PipelineRunStatus.SUCCESS}),
    PipelineRunStatus.SEND_ERROR: frozenset({PipelineRunStatus.ERROR}),
    # nothing follows these
    PipelineRunStatus.SUCCESS: frozenset(),
    PipelineRunStatus.ERROR: frozenset(),
    PipelineRunStatus.CANCELLED: frozenset(),
    PipelineRunStatus.RESOLVED: frozenset(),
}

TERMINAL_PIPELINE_RUN_STATUSES = tuple(
    status for status, allowed in PIPELINE_RUN_TRANSITIONS.items() if not allowed
)


def next_states(current: PipelineRunStatus) -> frozenset[PipelineRunStatus]:
    """Where a run may go from here. Empty for a terminal state."""
    allowed = PIPELINE_RUN_TRANSITIONS.get(current, frozenset())
    if not allowed:
        return allowed
    # A handler that raises is sent to SEND_ERROR, and cancellation is polled each loop, so
    # both are reachable from every state rather than chosen by a step.
    return allowed | {PipelineRunStatus.SEND_ERROR, PipelineRunStatus.CANCELLED}


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

    ROLLBACK (189) is deliberately excluded from `COLLECTION_KINDS`: a rollback reads no
    source, so `advances_last_seen` must not treat it as a sighting.
    """

    SCRAPE = "scrape"
    SHEET_IMPORT = "sheet_import"
    PEOPLE_EDIT = "people_edit"
    JURISDICTION_EDIT = "jurisdiction_edit"
    ROLLBACK = "rollback"


COLLECTION_KINDS = (ChangesetKind.SCRAPE, ChangesetKind.SHEET_IMPORT)


class DismissalReason(StrEnum):
    REJECTED = "rejected"  # a reviewer read the roster and said no
    CANCELLED = "cancelled"  # somebody stopped the run before it produced one
    ERRORED = "errored"  # the run ended without a roster; nobody decided
    SUPERSEDED = "superseded"  # a newer roster for this jurisdiction won


class ActivityType(StrEnum):
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
