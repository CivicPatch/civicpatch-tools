"""`changes_from_diff`: what the activity feed carries, read off two rosters.

Pure, no mocks. One source for every "what happened" — an edit, a publish and a rollback are
the same question asked of a different pair of rosters, which is why none of them diffs its own
payload any more.
"""

from datetime import datetime, timezone

import pytest

from core.projection.diff import roster_diff
from core.projection.facts import PostKey
from core.projection.people import Membership, Person
from core.projection.roster import Roster
from core.activity import changes_from_diff
from shared.utils.statuses import ActivityType

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
_BASE = "ocd-division/country:us/state:tx/place:alpha"
MAYOR = PostKey(organization_id="org-1", role_id="mayor", division_ocdid=_BASE)
CLERK = PostKey(organization_id="org-1", role_id="clerk", division_ocdid=_BASE)


def _person(person_id: str, name: str, post: PostKey = MAYOR, **overrides) -> Person:
    return Person(
        id=person_id,
        name=name,
        memberships=(Membership(post=post, opened_at=_T),),
        **overrides,
    )


def _changes(before: list[Person], after: list[Person], post_labels=None):
    first, second = Roster(people=tuple(before)), Roster(people=tuple(after))
    return changes_from_diff(first, second, roster_diff(first, second), post_labels)


def _types(changes):
    return [change.type for change in changes]


@pytest.mark.unit
def test_an_unchanged_roster_says_nothing():
    """A save that changed nothing must leave no trace: the editor sends every person, so
    saying the same thing twice is the normal case."""
    roster = [_person("p1", "Ann Lee")]

    assert _changes(roster, roster) == []


@pytest.mark.unit
def test_somebody_arriving_is_an_addition():
    changes = _changes([], [_person("p1", "Ann Lee")])

    assert _types(changes) == [ActivityType.ADD_PERSON]
    assert changes[0].payload.subject == "Ann Lee"


@pytest.mark.unit
def test_somebody_leaving_is_a_removal_and_is_still_named():
    """Only the roster they left knows their name, which is why both rosters are read."""
    changes = _changes([_person("p1", "Ann Lee")], [])

    assert _types(changes) == [ActivityType.DELETE_PERSON]
    assert changes[0].payload.subject == "Ann Lee"


@pytest.mark.unit
def test_a_changed_field_is_an_edit_carrying_what_moved():
    changes = _changes(
        [_person("p1", "Ann Lee")], [_person("p1", "Ann Lee", phones=("555",))]
    )

    assert _types(changes) == [ActivityType.EDIT_PERSON]
    field = changes[0].payload.fields[0]
    assert (field.field, field.before, field.after) == ("phones", (), ("555",))


@pytest.mark.unit
def test_one_person_s_edits_are_one_row():
    """Not a row per field: the feed reads as what somebody did, not as what a column did."""
    changes = _changes(
        [_person("p1", "Ann Lee")],
        [_person("p1", "Ann Lee-Park", phones=("555",))],
    )

    assert _types(changes) == [ActivityType.EDIT_PERSON]
    assert {field.field for field in changes[0].payload.fields} == {"name", "phones"}


@pytest.mark.unit
def test_a_move_names_the_post_it_left_and_the_one_it_arrived_in():
    """The fold keeps one membership per organization, so a move arrives as a membership
    leaving and another appearing — never as anything that says "moved"."""
    changes = _changes(
        [_person("p1", "Ann Lee", MAYOR)], [_person("p1", "Ann Lee", CLERK)]
    )

    assert _types(changes) == [ActivityType.ASSIGN_MEMBERSHIP]
    field = changes[0].payload.fields[0]
    assert (field.before, field.after) == (MAYOR.post_id, CLERK.post_id)


@pytest.mark.unit
def test_a_move_says_which_seats_when_it_is_given_their_names():
    """The whole point of `post_labels`. Without them the history page renders this row as
    `post: <uuid> -> <uuid>` and its collapsed badge as the bare field name, which is what
    `schemas.activity.RosterChange` warns about and what the fold path did until 2026-09-24."""
    changes = _changes(
        [_person("p1", "Ann Lee", MAYOR)],
        [_person("p1", "Ann Lee", CLERK)],
        {MAYOR.post_id: "Mayor", CLERK.post_id: "Clerk"},
    )

    field = changes[0].payload.fields[0]
    assert (field.before, field.after) == ("Mayor", "Clerk")
    # The badge shows `detail` where there is one, so it reads the seat rather than "post".
    assert changes[0].payload.detail == "Clerk"


@pytest.mark.unit
def test_a_seat_with_no_name_stays_identified_rather_than_blank():
    """Falling back to the id keeps the row truthful. Dropping it would lose the half of a move
    that does have a name."""
    changes = _changes(
        [_person("p1", "Ann Lee", MAYOR)],
        [_person("p1", "Ann Lee", CLERK)],
        {CLERK.post_id: "Clerk"},
    )

    field = changes[0].payload.fields[0]
    assert (field.before, field.after) == (MAYOR.post_id, "Clerk")


@pytest.mark.unit
def test_an_arrival_does_not_also_report_its_fields_or_its_seat():
    """Somebody added is one row. Their name and their office are not separate news."""
    changes = _changes([], [_person("p1", "Ann Lee")])

    assert _types(changes) == [ActivityType.ADD_PERSON]


@pytest.mark.unit
def test_the_feed_does_not_depend_on_the_order_the_people_arrive():
    """R6: two runs over the same rosters produce the same feed."""
    before = [_person("p1", "Ann Lee"), _person("p2", "Bo Nguyen")]
    after = [
        _person("p1", "Ann Lee-Park"),
        _person("p2", "Bo T. Nguyen"),
    ]

    forwards = _changes(before, after)
    backwards = _changes(list(reversed(before)), list(reversed(after)))

    assert [(c.type, c.payload.entity_id) for c in forwards] == [
        (c.type, c.payload.entity_id) for c in backwards
    ]
