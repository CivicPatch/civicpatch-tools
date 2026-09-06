"""What a card is worth, for ordering the review pool.

The other half of `review_pool`: that one decides membership, this one decides order.

⚠️ **Only the post issues reach the ordering today.** The five roster checks are computed at
read from the published and proposed rosters — neither of which SQL can derive — so they show
on the card but cannot sort the pool. `.scratch/2026-08-25-retire-review-json.md` phase 2 puts
them in `roster_issues` and restores the full score; until then the queue orders on unverified
posts, then recency.

Not in `changesets.py`: the score reads `posts` too, and importing posts there closes a cycle
(`changesets` → `posts` → `change_logs` → `changesets`).
"""

from typing import LiteralString, cast

from database.posts import JURISDICTIONS_FIRST_SCRAPE, POST_IS_VERIFIED
from shared.schemas import IssueCode

# How much a reviewer should care, per issue. Ordering on `jsonb_array_length` weighted every
# issue the same, so a ward-numbering gap outranked nothing and a new type was an
# unprioritisable +1.
_ISSUE_WEIGHT = {
    IssueCode.TOO_FEW_PEOPLE: 10,        # the roster is incomplete; publishing retires people
    IssueCode.DUPLICATE_UNIQUE_ROLE: 8,  # two mayors is a contradiction, not a judgement call
    IssueCode.DISPUTED_POST: 6,          # a human answered and the scrape disagrees
    IssueCode.ABSENT_PERSON: 5,          # someone we hold is gone
    IssueCode.MOVED_PERSON: 4,           # someone we hold is in a different seat
    IssueCode.NEW_PERSON: 3,             # someone arrived
    # Below NEW_PERSON: a person found in a post we have never seen raises both, which is one
    # event seen twice. Counted from `posts`, never stored, so its CASE arm never matches — the
    # entry is here so one table holds every weight.
    IssueCode.UNVERIFIED_POST: 2,
    # Above the numbering gap, below anyone arriving or leaving: a moved value is worth a
    # look but it is the commonest issue there is, so it must not outrank a lost person.
    IssueCode.CHANGED_FIELD: 2,
    IssueCode.DIVISION_NUMBERING_GAP: 1,
}
# A stored summary can still name a code since renamed out of the enum.
_UNKNOWN_ISSUE = 1


def _unverified_posts(jurisdiction_ocdid: str) -> str:
    """SQL counting posts nobody has vouched for.

    Same two predicates as `unverified_by_jurisdiction`, shared rather than restated: a queue
    scoring cards on issues the card does not show is worse than not scoring them at all.
    """
    return (
        f"(SELECT count(*) FROM posts "
        f"WHERE posts.jurisdiction_ocdid = {jurisdiction_ocdid} "
        f"AND NOT {POST_IS_VERIFIED} AND NOT {JURISDICTIONS_FIRST_SCRAPE})"
    )


def issue_count(jurisdiction_ocdid: str) -> LiteralString:
    """SQL for how many issues the queue can see from here.

    Undercounts the card, which also shows the five roster checks — see the module note.
    """
    return cast(LiteralString, _unverified_posts(jurisdiction_ocdid))


def issue_priority(jurisdiction_ocdid: str) -> LiteralString:
    """SQL scoring what a card costs a reviewer, to sort a queue on.

    Takes a column expression rather than assuming a table alias, so a caller that writes
    `FROM changesets` and one that does not can both use it. Composed from ints and that
    expression — no user input reaches it, which is what `sql.SQL`'s LiteralString guard
    cannot see for itself.
    """
    posts_weight = _ISSUE_WEIGHT[IssueCode.UNVERIFIED_POST]
    return cast(
        LiteralString,
        f"({_unverified_posts(jurisdiction_ocdid)} * {posts_weight})",
    )
