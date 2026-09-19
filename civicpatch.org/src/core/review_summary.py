"""A review card's issue list, from rosters already loaded.

Pure: `services.review_proposal` loads the inputs, this decides. The rosters are plain inputs so
a projection's output can feed it unchanged.
"""

from pydantic import BaseModel

from core.membership_proposal import ProposedChange
from core.people_edits import SURFACED_FIELDS
from core.post_issues import moved_person_issues, organizations_nobody_was_found_in
from shared.schemas import POST_FIELD, Issue, Person
from shared.utils.name_utils import person_list_to_identities
from shared.utils.review_utils import ReviewInputs, build_review_summary


# Mirrors `review_utils._build_row`.
class PeopleBySourceRow(BaseModel):
    name: str
    in_research: bool
    in_data: bool


class ReviewSummary(BaseModel):
    """Empty for a changeset we do not hold — nothing to compare against."""

    issues: list[Issue] = []
    people_by_source: list[PeopleBySourceRow] = []


def build_card_summary(
    published: list[dict],
    proposed: list[dict],
    changes: list[ProposedChange],
    unique_roles: list[str],
    unverified_posts: list[Issue],
    organization_names: dict[str, str],
) -> ReviewSummary:
    """The roster checks first, then the post checks."""
    roster_checks = build_review_summary(
        published,
        proposed,
        ReviewInputs(
            identities=person_list_to_identities([Person(**p) for p in published]),
            unique_roles=unique_roles,
            changed_field_names=list(SURFACED_FIELDS),
        ),
    )
    # `proposed` carries the picks in the organizations this changeset read, so a `post_id` here
    # is one that applies to the review in front of the reviewer.
    picked = {}
    for person in proposed:
        post_id = person.get(POST_FIELD)
        if post_id:
            picked[person["id"]] = post_id
    return ReviewSummary(
        issues=[
            *roster_checks["issues"],
            *unverified_posts,
            *moved_person_issues(changes, picked),
            *organizations_nobody_was_found_in(changes, organization_names),
        ],
        people_by_source=[
            PeopleBySourceRow(**row) for row in roster_checks["people_by_source"]
        ],
    )
