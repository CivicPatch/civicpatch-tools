"""A review card's issue list, from rosters already loaded.

Pure: `services.review_summary` loads the inputs, this decides. The rosters are plain inputs so
a projection's output can feed it unchanged.
"""

from collections import defaultdict

from pydantic import BaseModel
from shared.schemas import Issue
from shared.utils.divisions import numbered_division_label
from shared.utils.review_utils import (
    absent_person_issue,
    changed_field_issue,
    division_numbering_issues,
    duplicate_unique_role_issue,
    new_person_issue,
    too_few_people_issues,
)

from core.people_edits import SURFACED_FIELDS
from core.post_issues import (
    moved_person_issues_from_roster,
    organizations_nobody_was_found_in_from_roster,
)
from core.projection.diff import RosterDiff
from core.projection.people import Person as FoldPerson
from core.projection.roster import Roster


# Mirrors `review_utils._build_row`.
class PeopleBySourceRow(BaseModel):
    name: str
    in_research: bool
    in_data: bool


class ReviewSummary(BaseModel):
    """Empty for a changeset we do not hold — nothing to compare against."""

    issues: list[Issue] = []
    people_by_source: list[PeopleBySourceRow] = []


def _name_of(person: FoldPerson | None) -> str:
    return (person.name or person.id) if person else ""


def _absent_issues(published: Roster, diff: RosterDiff) -> list[Issue]:
    people = {person.id: person for person in published.people}
    return [
        absent_person_issue(_name_of(people.get(person_id)))
        for person_id in diff.only_before
    ]


def _new_issues(published: Roster, proposed: Roster, diff: RosterDiff) -> list[Issue]:
    # A first scrape has nothing to be new against: every person would raise one, and a
    # jurisdiction we hold nothing for could never auto-publish.
    if not published.people:
        return []
    people = {person.id: person for person in proposed.people}
    return [
        new_person_issue(_name_of(people.get(person_id)), person_id)
        for person_id in diff.only_after
    ]


def _too_few_issues(proposed: Roster) -> list[Issue]:
    return too_few_people_issues(len(proposed.people))


def _changed_field_issues(proposed: Roster, diff: RosterDiff) -> list[Issue]:
    names = {person.id: person.name or "" for person in proposed.people}
    return [
        changed_field_issue(
            change.field, names.get(change.person_id, ""), change.person_id
        )
        for change in diff.fields
        if change.field in SURFACED_FIELDS
    ]


def _duplicate_unique_role_issues(
    proposed: Roster, unique_role_ids: set[str]
) -> list[Issue]:
    wanted = {role_id.lower() for role_id in unique_role_ids}
    holders: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for person in proposed.people:
        for membership in person.memberships:
            role_id = membership.post.role_id.lower().strip()
            if role_id in wanted:
                holders[role_id].append((person.id, person.name or ""))
    return [
        duplicate_unique_role_issue(role_id, people)
        for role_id, people in holders.items()
        if len(people) > 1
    ]


def _division_numbering_issues(proposed: Roster) -> list[Issue]:
    return division_numbering_issues(
        [
            number
            for person in proposed.people
            for membership in person.memberships
            if (number := numbered_division_label(membership.post.division_ocdid)) is not None
        ]
    )


def _people_by_source(published: Roster, proposed: Roster) -> list[PeopleBySourceRow]:
    baseline = {person.name for person in published.people if person.name}
    discovered = {person.name for person in proposed.people if person.name}
    return [
        PeopleBySourceRow(
            name=name, in_research=name in baseline, in_data=name in discovered
        )
        for name in sorted(baseline | discovered)
    ]


def roster_summary(
    published: Roster,
    proposed: Roster,
    diff: RosterDiff,
    unique_role_ids: set[str],
) -> ReviewSummary:
    return ReviewSummary(
        issues=[
            *_absent_issues(published, diff),
            *_new_issues(published, proposed, diff),
            *_too_few_issues(proposed),
            *_changed_field_issues(proposed, diff),
            *_duplicate_unique_role_issues(proposed, unique_role_ids),
            *_division_numbering_issues(proposed),
        ],
        people_by_source=_people_by_source(published, proposed),
    )


def fold_card_summary(
    published: Roster,
    proposed: Roster,
    diff: RosterDiff,
    read_organization_ids: set[str],
    role_labels: dict[str, str],
    unique_role_ids: set[str],
    unverified_posts: list[Issue],
    organization_names: dict[str, str],
) -> ReviewSummary:
    """`roster_summary` plus the post checks, all over the fold. The proposal layer is not read:
    a move and an empty body are both statements about the two rosters."""
    roster = roster_summary(published, proposed, diff, unique_role_ids)
    return ReviewSummary(
        issues=[
            *roster.issues,
            *unverified_posts,
            *moved_person_issues_from_roster(published, proposed, diff, role_labels),
            *organizations_nobody_was_found_in_from_roster(
                published, proposed, read_organization_ids, organization_names
            ),
        ],
        people_by_source=roster.people_by_source,
    )
