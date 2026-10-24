"""What a card is worth, for ordering the review pool.

The other half of `review_pool`: that one decides membership, this one decides order.

⚠️ **Only the run's stored issues reach the ordering today** (`pipeline_run_issues`, through
`pipeline_runs.changeset_id`). A pending user report takes a card out of the pool (`UNDECIDED`),
so `changeset_issues` has nothing to add. The roster checks are computed at read from the
published and proposed rosters, which SQL cannot derive, so they show on the card but cannot
sort the pool until they are stored.

Not in `changesets.py`: importing it there closes a cycle (`changesets` → `posts` → `activity` →
`changesets`).
"""

from typing import LiteralString, cast

from shared.utils.statuses import PipelineIssueStatus, PipelineIssueType

# How much a reviewer should care, per stored issue type.
_ISSUE_WEIGHT = {
    PipelineIssueType.FEWER_THAN_EXPECTED: 10,  # the roster is short; publishing retires people
    PipelineIssueType.COST_CAP_REACHED: 10,     # the run stopped before it had the roster
    PipelineIssueType.USER_REPORTED: 8,         # a person flagged it
    PipelineIssueType.PIPELINE_ERROR: 5,
}
# A stored issue can still name a type since renamed out of the enum.
_UNKNOWN_ISSUE = 1


def _pending_issues(changeset_id: str, value: str) -> str:
    """SQL summing `value` over the pending issues of the run behind a changeset."""
    pending = PipelineIssueStatus.PENDING.value
    return (
        f"(SELECT coalesce(sum({value}), 0) FROM pipeline_run_issues issue "
        f"JOIN pipeline_runs run ON run.id = issue.pipeline_run_id "
        f"WHERE run.changeset_id = {changeset_id} AND issue.status = '{pending}')"
    )


def _weight() -> str:
    arms = " ".join(f"WHEN '{issue_type.value}' THEN {weight}" for issue_type, weight in _ISSUE_WEIGHT.items())
    return f"CASE issue.issue_type {arms} ELSE {_UNKNOWN_ISSUE} END"


def issue_count(changeset_id: str) -> LiteralString:
    """SQL for how many pending run issues a card has. Undercounts the card, which also shows
    the roster checks; see the module note."""
    return cast(LiteralString, _pending_issues(changeset_id, "1"))


def issue_priority(changeset_id: str) -> LiteralString:
    """SQL scoring what a card costs a reviewer, to sort a queue on.

    Takes a column expression rather than assuming a table alias. Composed from enum values, ints
    and that expression; no user input reaches it, which is what `sql.SQL`'s LiteralString guard
    cannot see for itself.
    """
    return cast(LiteralString, _pending_issues(changeset_id, _weight()))
