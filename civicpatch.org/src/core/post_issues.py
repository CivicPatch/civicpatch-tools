"""Review issues about posts rather than about people.

Pure. Computed from stored posts every time a card is opened, never written — so a change to
what counts as an issue reaches every card at once instead of only the scrapes run after a
backfill.

A post outlives the scrape that minted it, which is the whole point: superseding a request
dismisses the roster it proposed, and the post it minted stays unanswered.
"""

from collections.abc import Mapping

from shared.schemas import POST_FIELD, Issue, IssueCode

from core.membership_label import derive_post_label
from core.membership_proposal import Disposition, ProposedChange


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


def moved_person_issues(
    changes: list[ProposedChange], picked: Mapping[str, str]
) -> list[Issue]:

    return [
        Issue(
            code=IssueCode.MOVED_PERSON,
            message=(
                f"Moved from {change.from_post_label} to {change.post_label}"
                if change.from_post_label
                else f"Moved to {change.post_label}"
            ),
            person_ids=[change.person_id],
            field=POST_FIELD,
        )
        for change in changes
        if change.disposition is Disposition.MOVED and change.person_id not in picked
    ]


def disputed_post_issues(
    changes: list[ProposedChange], picked: Mapping[str, str]
) -> list[Issue]:
    """A pick the derivation no longer agrees with.

    An accepted post outlives the scrape that prompted it — that is the point of recording a
    human's answer. But it also means a parser fix can no longer move that person, so a
    disagreement has to be said out loud rather than silently resolved either way.

    A pick names an existing post, so if the derivation reached the same identity
    `ids_by_identity` would have returned the same id. Anything else is a real difference,
    including a derived identity that has no post row yet.
    """
    return [
        Issue(
            code=IssueCode.DISPUTED_POST,
            message=f"Picked a different post — this scrape says {change.post_label}",
            person_ids=[change.person_id],
            field=POST_FIELD,
        )
        for change in changes
        if change.disposition is not Disposition.ABSENT
        and (pick := picked.get(change.person_id))
        and pick != change.post_id
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
