"""Review issues about posts rather than about people.

Pure. Computed from stored posts every time a card is opened, never written — so a change to
what counts as an issue reaches every card at once instead of only the scrapes run after a
backfill.

A post outlives the scrape that minted it, which is the whole point: superseding a request
dismisses the roster it proposed, and the post it minted stays unanswered.
"""

from collections import defaultdict
from collections.abc import Mapping

from shared.schemas import POST_FIELD, Issue, IssueCode

from core.membership_label import derive_post_label
from core.projection.diff import RosterDiff
from core.projection.facts import PostKey
from core.projection.roster import Roster


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


def _post_index(*rosters: Roster) -> dict[str, PostKey]:
    """Every post either roster names, by id, so a diff's post ids can be read back to a key."""
    return {
        membership.post.post_id: membership.post
        for roster in rosters
        for person in roster.people
        for membership in person.memberships
    }


def _by_person_and_organization(
    pairs: tuple[tuple[str, str], ...], index: dict[str, PostKey]
) -> dict[tuple[str, str], PostKey]:
    grouped: dict[tuple[str, str], PostKey] = {}
    for person_id, post_id in pairs:
        post = index.get(post_id)
        if post is not None:
            grouped[(person_id, post.organization_id)] = post
    return grouped


def _post_name_from_key(post: PostKey, role_labels: Mapping[str, str]) -> str:
    return derive_post_label(
        role_labels.get(post.role_id, post.role_id), post.division_ocdid
    )


def moved_person_issues_from_roster(
    published: Roster,
    proposed: Roster,
    diff: RosterDiff,
    role_labels: Mapping[str, str],
) -> list[Issue]:
    """A move is one organization's post changing for one person. `RosterDiff` names posts by id
    and the message names them by role and division, so the keys come from the rosters and the
    role labels from the taxonomy.

    A change of organization is an absence and an arrival, not a move: `propose` compared posts
    within one organization, and a body's person turning up in another body was not a move.
    """
    index = _post_index(published, proposed)
    before = _by_person_and_organization(diff.memberships_only_before, index)
    after = _by_person_and_organization(diff.memberships_only_after, index)
    return [
        Issue(
            code=IssueCode.MOVED_PERSON,
            message=(
                f"Moved from {_post_name_from_key(from_post, role_labels)} "
                f"to {_post_name_from_key(to_post, role_labels)}"
            ),
            person_ids=[person_id],
            field=POST_FIELD,
        )
        for (person_id, organization_id), from_post in before.items()
        if (to_post := after.get((person_id, organization_id))) is not None
        and to_post != from_post
    ]


def _members_by_organization(roster: Roster) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for person in roster.people:
        for membership in person.memberships:
            grouped[membership.post.organization_id].add(person.id)
    return grouped


def organizations_nobody_was_found_in_from_roster(
    published: Roster,
    proposed: Roster,
    read_organization_ids: set[str],
    organization_names: Mapping[str, str],
) -> list[Issue]:
    """An organization the changeset read whose published members are all gone **from the whole
    roster**. `propose` marks a departure only when the person is unseen everywhere in the
    scrape, so a member who moved to another organization is not a departure and does not raise
    this.
    """
    published_members = _members_by_organization(published)
    proposed_members = _members_by_organization(proposed)
    proposed_people = {person.id for person in proposed.people}
    return [
        Issue(
            code=IssueCode.NOBODY_FOUND_IN_ORGANIZATION,
            message=(
                f"Nobody found in "
                f"{organization_names.get(organization_id) or 'one organization'}"
            ),
        )
        for organization_id, members in published_members.items()
        if organization_id in read_organization_ids
        and not proposed_members.get(organization_id)
        and members - proposed_people
    ]


