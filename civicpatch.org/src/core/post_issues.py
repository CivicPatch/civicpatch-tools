"""Review issues about posts rather than about people.

Pure. Computed from stored posts every time a card is opened, never written — so a change to
what counts as an issue reaches every card at once instead of only the scrapes run after a
backfill.

A post outlives the scrape that minted it, which is the whole point: superseding a request
dismisses the roster it proposed, and the post it minted stays unanswered.
"""

from core.membership_label import derive_post_label
from core.membership_proposal import Disposition, ProposedChange
from shared.schemas import POST_FIELD, Issue, IssueCode


def _post_name(post: dict) -> str:
    return derive_post_label(post["role_label"], post["division_ocdid"])


def unverified_post_issues(posts: list[dict]) -> list[Issue]:
    return [
        Issue(
            code=IssueCode.UNVERIFIED_POST,
            message=f"Unverified post: {_post_name(post)}",
            person_ids=[],
        )
        for post in posts
    ]


def moved_person_issues(changes: list[ProposedChange]) -> list[Issue]:
    """A move between posts, which no field diff can see.

    `post_id` on a person is the reviewer's pick and is null on both sides until they make one,
    so someone becoming Council President compares equal on every field. Anchoring to `post_id`
    is what puts the Post row on their card at all.
    """
    return [
        Issue(
            code=IssueCode.MOVED_PERSON,
            message=f"Moved to {change.post_label}",
            person_ids=[change.person_id],
            field=POST_FIELD,
        )
        for change in changes
        if change.disposition is Disposition.MOVED
    ]


def append_post_issues(summary: dict, posts: list[Issue]) -> dict:
    """One issue list for the card, the roster checks first.

    Both sides arrive as dicts — the roster checks dumped by the caller, a post issue dumped
    here. The card reads one list and does not care which check produced a row.
    """
    return {
        **summary,
        "issues": [
            *(summary.get("issues") or []),
            *(issue.model_dump() for issue in posts),
        ],
    }
