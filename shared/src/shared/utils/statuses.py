from enum import StrEnum


class PipelineRunStatus(StrEnum):
    """The lifecycle every pipeline shares. Each pipeline's own steps are a StrEnum in its runner
    (`PeopleCollectorStep`, `GoverningLawCollectorStep`); `pipeline_runs.status` stores either as text."""

    # civicpatch.org's, before a pipeline starts
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    # every pipeline's first state, and where the engine sends a step that raised
    INIT = "INIT"
    SEND_ERROR = "SEND_ERROR"
    # the ends
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


# Where every pipeline's run ends, whichever pipeline it is. civicpatch.org reads this to tell a
# finished run; each pipeline's graph must end on exactly these (test_engine.py holds them to it).
TERMINAL_PIPELINE_RUN_STATUSES = (
    PipelineRunStatus.SUCCESS,
    PipelineRunStatus.ERROR,
    PipelineRunStatus.CANCELLED,
    PipelineRunStatus.RESOLVED,
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
    source, so it must not date a jurisdiction's last collection.
    """

    SCRAPE = "scrape"
    SHEET_IMPORT = "sheet_import"
    ROSTER_EDIT = "roster_edit"
    JURISDICTION_EDIT = "jurisdiction_edit"
    ROLLBACK = "rollback"


COLLECTION_KINDS = (ChangesetKind.SCRAPE, ChangesetKind.SHEET_IMPORT)


class PipelineRunKind(StrEnum):
    """Which pipeline a `pipeline_runs` row is an attempt of. The run machinery (cap, `llm_calls`,
    issues, cancel, the stale sweep) is shared; the scrape's scheduling reads only its own kind."""

    PEOPLE_COLLECTOR = "people_collector"
    GOVERNING_LAW_COLLECTOR = "governing_law_collector"
    ORGANIZATIONS_COLLECTOR = "organizations_collector"


class DismissalReason(StrEnum):
    REJECTED = "rejected"  # a reviewer read the roster and said no
    CANCELLED = "cancelled"  # somebody stopped the run before it produced one
    ERRORED = "errored"  # the run ended without a roster; nobody decided
    SUPERSEDED = "superseded"  # a newer roster for this jurisdiction won
    EXPIRED = "expired"  # a sheet import nobody decided within a week


class PullRequestLabel(StrEnum):
    """What cp.org labels its open-data PRs with. A cross-repo contract: open-data's merge gates
    (scripts/github_actions/merge_config_pr.py, merge_jurisdiction_pr.py) merge all three, so a
    rename here without the same change there stops merging silently."""

    ADMIN = "civicpatch:admin"
    MAINTAINER = "civicpatch:maintainer"
    SYSTEM = "civicpatch:system"


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
    # An open-data config file synced after its PR merged; its role changes get their own rows.
    SYNC_JURISDICTION_CONFIG = "sync_jurisdiction_config"
    # Not a roster change — a run beginning or settling, not a change to what the roster is.
    # `changeset_id` is always null on start (nothing has been minted yet); on end it is set
    # only when the run succeeded far enough to mint one — a failed or cancelled run has none.
    PIPELINE_RUN_START = "pipeline_run_start"
    PIPELINE_RUN_END = "pipeline_run_end"
    # A curated sheet's rows landing on the import's batch page, never the review pool.
    # Publishing it there is a separate, later `PUBLISH_REVIEW`.
    SHEET_IMPORT = "sheet_import"


# What changes published data, and so what the outward mirrors (open-data, the sheet) sweep on.
# An allowlist: a type that only proposes (an import, a run ending) must not trigger a commit
# that credits it. Every `ActivityType` sits in exactly one of these two sets.
PUBLISHED_CHANGE_TYPES = frozenset({
    ActivityType.PUBLISH_REVIEW,
    ActivityType.ADD_PERSON,
    ActivityType.EDIT_PERSON,
    ActivityType.DELETE_PERSON,
    ActivityType.EDIT_JURISDICTION,
    ActivityType.ADD_POST,
    ActivityType.EDIT_POST,
    ActivityType.DELETE_POST,
    ActivityType.ASSIGN_MEMBERSHIP,
    ActivityType.ASSERT_FIELD,
})

UNPUBLISHED_ACTIVITY_TYPES = frozenset({
    # A dismissal ends a review without moving a row.
    ActivityType.DISMISS_REVIEW,
    # Global: no jurisdiction to sweep; the next change in each state carries the new wording.
    ActivityType.ADD_ROLE,
    ActivityType.EDIT_ROLE,
    ActivityType.DELETE_ROLE,
    ActivityType.REORDER_ROLES,
    ActivityType.SYNC_JURISDICTION_CONFIG,
    # Proposals: nothing is published until a later `PUBLISH_REVIEW`.
    ActivityType.PIPELINE_RUN_START,
    ActivityType.PIPELINE_RUN_END,
    ActivityType.SHEET_IMPORT,
})

# Nearly every activity type is audit trail only — read from the table, never watched — so this
# names the ones actually worth a live push.
LIVE_ACTIVITY_TYPES = frozenset({
    ActivityType.PUBLISH_REVIEW,
    ActivityType.PIPELINE_RUN_START,
    ActivityType.PIPELINE_RUN_END,
    ActivityType.SHEET_IMPORT,
})

# Fungible among LIVE_ACTIVITY_TYPES: interchangeable events where a listener only cares "how
# many, of what kind" happened, not which specific one — a state batch starting fifty runs is
# the case this exists for. `PUBLISH_REVIEW` is deliberately absent: each publish is its own
# notable thing, and collapsing it into a count would be a real loss, not tidying.
GROUPABLE_ACTIVITY_TYPES = frozenset({
    ActivityType.PIPELINE_RUN_START,
    ActivityType.PIPELINE_RUN_END,
    ActivityType.SHEET_IMPORT,
})


class EntityType(StrEnum):
    """What a claim is about. One definition: the fold and the write side both read this one.

    Facts can be claimed about too -- a withdraw names one, and a split is a `person_id` claim
    on a record.
    """

    PERSON = "person"
    POST = "post"
    MEMBERSHIP = "membership"
    JURISDICTION = "jurisdiction"
    ORGANIZATION = "organization"
    SOURCE_RECORD = "source_record"
    SOURCE_PAGE = "source_page"
    CLAIM = "claim"


class ClaimKind(StrEnum):
    # "This value stands." One per scalar field; one per element on a list field.
    ACCEPT = "accept"
    # "Never this value." Suppresses that value only, so the scraper keeps looking and a
    # genuinely new answer still reaches review.
    REJECT = "reject"
    # "This fact no longer counts." Names a whole row, carries no field and no value, and can
    # itself be withdrawn: that is undo.
    WITHDRAW = "withdraw"
