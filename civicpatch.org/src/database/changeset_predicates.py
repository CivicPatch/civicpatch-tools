"""The SQL vocabulary every changeset query is written in.

Split out of `changesets.py` 2026-09-05. Six modules imported that file for nothing but a
string; they now depend on the vocabulary instead of on the table, so the table can change
shape without them caring.

Unaliased throughout, per CLAUDE.md: a fragment that demands its caller alias a table is a
runtime error waiting, never a typecheck one. The state predicates derive from
`ChangesetState` rather than restating it — see `_in_state`.
"""

from core.changeset_lifecycle import ChangesetState
from database.review_sessions import (
    ReviewSessionEntryStatus,
)
from shared.utils.statuses import (
    ChangesetKind,
    PipelineIssueStatus,
    PipelineIssueType,
)

PUBLISHED = f"changesets.changeset_state IN ('{ChangesetState.PUBLISHED.value}')"

# Both terminal states. The complement of open, and the counterpart to `resolved_by_user_id`.
RESOLVED = (
    "changesets.changeset_state IN "
    f"('{ChangesetState.PUBLISHED.value}', '{ChangesetState.DISMISSED.value}')"
)

# Open, minus the one kind that is never reviewed: a jurisdiction edit is born published, so it
# has no in-flight phase to be in.
WORK_IN_FLIGHT = (
    f"changesets.changeset_state IN ('{ChangesetState.OPEN.value}') "
    f"AND changesets.kind != '{ChangesetKind.JURISDICTION_EDIT.value}'"
)

# Duplicates `DismissalReason`; kept only because the SQL fragments below splice it.
DISMISSED_SUPERSEDED = "superseded"

# A scrape still awaiting human review. Unaliased; callers use `FROM changesets` bare.
AVAILABLE_FOR_REVIEW = (
    "EXISTS (SELECT 1 FROM source_records sr WHERE sr.changeset_id = changesets.id) "
    # Composed, not restated: widening one used to leave the two disagreeing.
    f"AND {WORK_IN_FLIGHT} "
    "AND NOT EXISTS ("
    "SELECT 1 FROM issues i "
    f"WHERE i.issue_type = '{PipelineIssueType.USER_REPORTED.value}' "
    "AND changesets.id::text = ANY(i.changeset_ids) "
    f"AND i.status NOT IN ('{PipelineIssueStatus.RESOLVED.value}', '{PipelineIssueStatus.SUPERSEDED.value}')"
    ")"
)

# The run behind a changeset. No run — an import or a hand edit — answers NULL.
RUN_IN_FLIGHT = (
    "EXISTS (SELECT 1 FROM pipeline_runs "
    "WHERE pipeline_runs.changeset_id = changesets.id AND pipeline_runs.finished_at IS NULL)"
)
RUN_STATUS = "(SELECT status FROM pipeline_runs WHERE pipeline_runs.changeset_id = changesets.id)"
RUN_PROGRESS = "(SELECT progress FROM pipeline_runs WHERE pipeline_runs.changeset_id = changesets.id)"

# Request supercede can dismiss.
# Sweep should not dismiss a card still in the queue.
SWEEPABLE = (
    f"{AVAILABLE_FOR_REVIEW} "
    "AND EXISTS ("
    "SELECT 1 FROM jurisdictions j "
    "WHERE j.jurisdiction_ocdid = changesets.jurisdiction_ocdid "
    "AND j.status = 'active'"
    ")"
)

HELD_BY_REVIEWER = (
    "EXISTS ("
    "SELECT 1 FROM review_session_entries e "
    "WHERE changesets.id::text = ANY(e.changeset_ids) "
    # `.value`, not the member: pyright narrows a StrEnum's `.value` to a literal, while
    # interpolating the member itself goes through `__str__` and types as `str` — which breaks
    # `LiteralString` for every query that splices this.
    f"AND (e.status IN ('{ReviewSessionEntryStatus.SAVED.value}', "
    f"'{ReviewSessionEntryStatus.RESOLVED.value}') "
    f"OR (e.status = '{ReviewSessionEntryStatus.CLAIMED.value}' AND e.created_at >= NOW() - %s))"
    ")"
)


# When a source was last read for a jurisdiction and published — the fact
# `jurisdictions.scraped_at` was meant to hold and did not: it was stamped on *every* publish,
# so ten hand edits had dated a "scrape" for jurisdictions where nothing was scraped.
#
# `updated_at`, not `created_at`: that is when the content was confirmed, and the key
# superseding already orders on. Collection kinds only, which is the same rule
# `publish_request`'s `advances_last_seen` applies to `memberships.last_seen_at` — a hand edit
# reads no source, so it may not date one.
#
# A join, not a correlated subquery: one aggregate scan, and it needs no alias on
# `jurisdictions`, so a query that already aliases it `j` takes it unchanged. **One per
# statement** — a query with several `FROM jurisdictions j` clauses gets `DuplicateAlias` if
# each one adds it.
#
# The kinds are spelled out rather than joined from `COLLECTION_KINDS` so this stays a
# `LiteralString`; `test_last_collected_names_every_collection_kind` binds the two.
LAST_COLLECTED_JOIN = (
    "LEFT JOIN ("
    "SELECT jurisdiction_ocdid, max(updated_at) AS last_collected_at "
    "FROM changesets "
    "WHERE published_at IS NOT NULL "
    f"AND kind IN ('{ChangesetKind.SCRAPE.value}', '{ChangesetKind.SHEET_IMPORT.value}') "
    "GROUP BY jurisdiction_ocdid"
    ") collected USING (jurisdiction_ocdid)"
)

# What the join exposes, so a WHERE clause reads without hunting for the join.
LAST_COLLECTED_AT = "collected.last_collected_at"


# When a jurisdiction was last *tried*, not last published. A dismissed card and an errored run
# both leave no published changeset, so a pool keyed on publishes re-offers them at once.
LAST_ATTEMPT_JOIN = (
    "LEFT JOIN ("
    "SELECT jurisdiction_ocdid, max(created_at) AS last_attempt_at "
    "FROM pipeline_runs GROUP BY jurisdiction_ocdid"
    ") attempts USING (jurisdiction_ocdid)"
)
LAST_ATTEMPT_AT = "attempts.last_attempt_at"

# A state's own cadence is the cooldown. NULL means manual: no schedule, and nothing excluded.
CADENCE_JOIN = "LEFT JOIN state_settings ss ON ss.state = j.state"
OFF_COOLDOWN = (
    "(ss.cadence_days IS NULL"
    f" OR {LAST_ATTEMPT_AT} IS NULL"
    f" OR {LAST_ATTEMPT_AT} < now() - make_interval(days => ss.cadence_days))"
)
