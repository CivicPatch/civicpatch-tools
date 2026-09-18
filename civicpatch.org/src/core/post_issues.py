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
from core.membership_proposal import MembershipDisposition, ProposedChange


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
                f"Moved from {change.from_post.label} to {change.post.label}"
                if change.from_post
                else f"Moved to {change.post.label}"
            ),
            person_ids=[change.person_id],
            field=POST_FIELD,
        )
        for change in changes
        if change.disposition is MembershipDisposition.MOVED and change.person_id not in picked
    ]


def organizations_nobody_was_found_in(
    changes: list[ProposedChange], names: Mapping[str, str]
) -> list[Issue]:
    """One issue per organization whose every proposal is a departure.

    Nothing publishes there: closing skips an organization with nobody in it, so the roster it
    holds today survives untouched. That is right when the scrape never read a page for it, and
    wrong when it read one and came back empty, and only a person can tell those apart, which is
    why this is a review issue rather than a pipeline one.
    """
    people: dict[str, int] = {}
    departures: dict[str, int] = {}
    for change in changes:
        people[change.organization_id] = people.get(change.organization_id, 0) + 1
        if change.disposition is MembershipDisposition.ABSENT:
            departures[change.organization_id] = departures.get(change.organization_id, 0) + 1
    return [
        Issue(
            code=IssueCode.NOBODY_FOUND_IN_ORGANIZATION,
            message=f"Nobody found in {names.get(organization_id) or 'one organization'}",
        )
        for organization_id, count in people.items()
        if departures.get(organization_id, 0) == count
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
