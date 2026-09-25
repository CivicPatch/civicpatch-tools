"""What `roster_diff` must answer.

The one diff: the projection diff (stored against derived), review cards, and the history loop
are all this over two rosters.
"""

from datetime import datetime, timezone

import pytest

from core.projection.diff import (
    FieldDifference,
    MembershipFieldDifference,
    on_roster,
    roster_diff,
)
from core.projection.facts import PostKey
from core.projection.people import Membership, Person
from core.projection.roster import Roster

COUNCIL = "11111111-1111-1111-1111-111111111111"
BASE = "ocd-division/country:us/state:tx/place:alpha"
MAYOR = PostKey(organization_id=COUNCIL, role_id="mayor", division_ocdid=BASE)
MEMBER = PostKey(
    organization_id=COUNCIL, role_id="council-member", division_ocdid=BASE
)


_T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def membership(post: PostKey, **fields) -> Membership:
    return Membership(post=post, opened_at=_T, **fields)


def person(id: str, *posts: str, **fields) -> Person:
    return Person(
        id=id,
        name=fields.pop("name", id.title()),
        memberships=tuple(membership(post) for post in posts),
        **fields,
    )


def roster(*people: Person) -> Roster:
    return Roster(people=people)


@pytest.mark.unit
def test_the_same_roster_has_no_diff():
    same = roster(person("alice", MAYOR), person("bob", MEMBER))

    assert roster_diff(same, same).empty


@pytest.mark.unit
def test_a_person_on_one_side_only():
    diff = roster_diff(roster(person("alice", MAYOR)), roster(person("bob", MEMBER)))

    assert diff.only_before == ("alice",)
    assert diff.only_after == ("bob",)


@pytest.mark.unit
def test_a_changed_field_names_both_values():
    diff = roster_diff(
        roster(person("alice", MAYOR, phones=("555-0001",))),
        roster(person("alice", MAYOR, phones=("555-0002",))),
    )

    assert diff.fields == (
        FieldDifference(
            person_id="alice", field="phones", before=("555-0001",), after=("555-0002",)
        ),
    )
    assert diff.only_before == diff.only_after == ()


@pytest.mark.unit
def test_a_membership_that_moved():
    diff = roster_diff(roster(person("alice", MAYOR)), roster(person("alice", MEMBER)))

    assert diff.memberships_only_before == (("alice", MAYOR.post_id),)
    assert diff.memberships_only_after == (("alice", MEMBER.post_id),)
    assert diff.fields == ()


@pytest.mark.unit
def test_a_membership_both_sides_hold_compares_column_by_column():
    before = Person(id="alice", memberships=(membership(MAYOR, label="Mayor"),))
    after = Person(id="alice", memberships=(membership(MAYOR, label="Mayor Pro Tem"),))

    diff = roster_diff(roster(before), roster(after))

    assert diff.membership_fields == (
        MembershipFieldDifference(
            person_id="alice", post_id=MAYOR.post_id, field="label", before="Mayor",
            after="Mayor Pro Tem",
        ),
    )
    assert diff.memberships_only_before == diff.memberships_only_after == ()


@pytest.mark.unit
def test_seen_dates_are_not_compared():
    """The fold dates by record, the stored rows by changeset; step 15 replaces both."""
    before = Person(id="alice", memberships=(membership(MAYOR),))
    later = _T.replace(year=2027)
    after = Person(
        id="alice",
        memberships=(
            Membership(post=MAYOR, opened_at=later),
        ),
    )

    assert roster_diff(roster(before), roster(after)).empty


@pytest.mark.unit
def test_on_roster_keeps_only_people_holding_a_membership():
    """The stored `people` table keeps retired people's rows; the fold does not write them, so
    the projection diff compares the people on the roster."""
    kept = on_roster(roster(person("alice", MAYOR), person("retired")))

    assert [p.id for p in kept.people] == ["alice"]


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_people_arrive():
    """R6."""
    before = roster(person("alice", MAYOR), person("bob", MEMBER, name="Bob L."))
    after = roster(person("carol", MAYOR), person("bob", MEMBER))

    forwards = roster_diff(before, after)
    backwards = roster_diff(
        Roster(people=tuple(reversed(before.people))), Roster(people=tuple(reversed(after.people)))
    )

    assert forwards == backwards
