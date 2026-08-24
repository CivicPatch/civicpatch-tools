"""How the review queue weighs and counts a card.

Not in `requests.py`: the score reads `posts` too, and importing posts there closes a cycle
(`requests` → `posts` → `change_logs` → `requests`).
"""

from typing import LiteralString, cast

from database.posts import POST_IS_VERIFIED
from shared.schemas import IssueCode

# How much a reviewer should care, per issue. Ordering on `jsonb_array_length` weighted every
# issue the same, so a ward-numbering gap outranked nothing and a new type was an
# unprioritisable +1.
_ISSUE_WEIGHT = {
    IssueCode.TOO_FEW_PEOPLE: 10,        # the roster is incomplete; publishing retires people
    IssueCode.DUPLICATE_UNIQUE_ROLE: 8,  # two mayors is a contradiction, not a judgement call
    IssueCode.ABSENT_OFFICIAL: 5,        # someone we hold is gone
    IssueCode.NEW_OFFICIAL: 3,           # someone arrived
    # Below NEW_OFFICIAL: a person found in a post we have never seen raises both, which is one
    # event seen twice. Counted from `posts`, never stored, so its CASE arm never matches — the
    # entry is here so one table holds every weight.
    IssueCode.UNVERIFIED_POST: 2,
    IssueCode.DIVISION_NUMBERING_GAP: 1,
}
# A stored summary can still name a code since renamed out of the enum.
_UNKNOWN_ISSUE = 1


def _unverified_posts(jurisdiction_ocdid: str) -> str:
    """SQL counting posts nobody has vouched for."""
    return (
        f"(SELECT count(*) FROM posts "
        f"WHERE posts.jurisdiction_ocdid = {jurisdiction_ocdid} AND NOT {POST_IS_VERIFIED})"
    )


def _stored_weight(review_json: str) -> str:
    cases = " ".join(
        f"WHEN '{code.value}' THEN {weight}" for code, weight in _ISSUE_WEIGHT.items()
    )
    return (
        f"(SELECT COALESCE(sum(CASE issue->>'code' {cases} ELSE {_UNKNOWN_ISSUE} END), 0) "
        f"FROM jsonb_array_elements(COALESCE({review_json}, '{{}}'::jsonb)->'issues') issue)"
    )


def issue_count(review_json: str, jurisdiction_ocdid: str) -> LiteralString:
    """SQL for how many issues a card holds.

    The same two sources the review endpoint appends together — or the queue's badge disagrees
    with the card it opens.
    """
    return cast(
        LiteralString,
        f"(COALESCE(jsonb_array_length({review_json}->'issues'), 0)"
        f" + {_unverified_posts(jurisdiction_ocdid)})",
    )


def issue_priority(review_json: str, jurisdiction_ocdid: str) -> LiteralString:
    """SQL scoring what a card costs a reviewer, to sort a queue on.

    Takes column expressions rather than assuming table aliases, so a caller that writes
    `FROM requests r` and one that does not can both use it. Composed from enum values, ints
    and those expressions — no user input reaches it, which is what `sql.SQL`'s LiteralString
    guard cannot see for itself.
    """
    posts_weight = _ISSUE_WEIGHT[IssueCode.UNVERIFIED_POST]
    return cast(
        LiteralString,
        f"({_stored_weight(review_json)}"
        f" + {_unverified_posts(jurisdiction_ocdid)} * {posts_weight})",
    )
