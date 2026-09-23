"""The two-roster diff: what changes between one roster and another.

One function for every "what changed" in the model:

    roster_diff(stored, derived)                       the projection diff, R6, step 8's dry run
    roster_diff(derive(published), derive(+ X))        a review card, a batch count, a rollback preview
    roster_diff(roster at t, roster at t + 1)          the history loop

Memberships compare by post id. The stored side's are computed from each post's key, since
today's post ids are random and the fold's are `uuid5` over the key. A membership both sides
hold is then compared column by column, since those are what the writer will produce.
"""

from pydantic import BaseModel

from core.projection.people import Membership, Person
from core.projection.roster import Roster

COMPARED_FIELDS = (
    "name",
    "other_names",
    "phones",
    "emails",
    "urls",
    "source_urls",
    "image",
    "cdn_image",
)


COMPARED_MEMBERSHIP_FIELDS = (
    "label",
    "start_date",
    "end_date",
    "designations",
    "unmatched_text",
    "sources",
    "extra_roles",
)


class FieldDifference(BaseModel, frozen=True):
    person_id: str
    field: str
    before: object
    after: object


class MembershipFieldDifference(BaseModel, frozen=True):
    person_id: str
    post_id: str
    field: str
    before: object
    after: object


class RosterDiff(BaseModel, frozen=True):
    only_before: tuple[str, ...] = ()
    only_after: tuple[str, ...] = ()
    fields: tuple[FieldDifference, ...] = ()
    memberships_only_before: tuple[tuple[str, str], ...] = ()
    memberships_only_after: tuple[tuple[str, str], ...] = ()
    membership_fields: tuple[MembershipFieldDifference, ...] = ()

    @property
    def empty(self) -> bool:
        return not (
            self.only_before
            or self.only_after
            or self.fields
            or self.memberships_only_before
            or self.memberships_only_after
            or self.membership_fields
        )


def on_roster(roster: Roster) -> Roster:
    """Only the people holding an open membership. The stored `people` table keeps retired
    people's rows as history, which the fold does not write, so the projection diff compares
    rosters rather than tables."""
    return Roster(people=tuple(person for person in roster.people if person.memberships))


def _memberships(people: dict[str, Person]) -> dict[tuple[str, str], Membership]:
    return {
        (person.id, membership.post_id): membership
        for person in people.values()
        for membership in person.memberships
    }


def roster_diff(before: Roster, after: Roster) -> RosterDiff:
    people_before = {person.id: person for person in before.people}
    people_after = {person.id: person for person in after.people}

    fields = [
        FieldDifference(
            person_id=person_id,
            field=field,
            before=getattr(people_before[person_id], field),
            after=getattr(people_after[person_id], field),
        )
        for person_id in sorted(people_before.keys() & people_after.keys())
        for field in COMPARED_FIELDS
        if getattr(people_before[person_id], field) != getattr(people_after[person_id], field)
    ]

    memberships_before = _memberships(people_before)
    memberships_after = _memberships(people_after)
    membership_fields = [
        MembershipFieldDifference(
            person_id=person_id,
            post_id=post_id,
            field=field,
            before=getattr(memberships_before[(person_id, post_id)], field),
            after=getattr(memberships_after[(person_id, post_id)], field),
        )
        for person_id, post_id in sorted(memberships_before.keys() & memberships_after.keys())
        for field in COMPARED_MEMBERSHIP_FIELDS
        if getattr(memberships_before[(person_id, post_id)], field)
        != getattr(memberships_after[(person_id, post_id)], field)
    ]

    return RosterDiff(
        only_before=tuple(sorted(people_before.keys() - people_after.keys())),
        only_after=tuple(sorted(people_after.keys() - people_before.keys())),
        fields=tuple(fields),
        memberships_only_before=tuple(
            sorted(memberships_before.keys() - memberships_after.keys())
        ),
        memberships_only_after=tuple(
            sorted(memberships_after.keys() - memberships_before.keys())
        ),
        membership_fields=tuple(membership_fields),
    )
