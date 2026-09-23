"""`membership_rows` and `membership_role_rows`: a derived roster as the rows B's writer inserts."""

import json
from datetime import datetime, timezone

import pytest
from shared.utils.membership_ids import membership_id

from core.projection.membership_details import MembershipSource
from core.projection.people import Membership, Person
from database.projection import membership_role_rows, membership_rows

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
_LATER = datetime(2026, 6, 1, tzinfo=timezone.utc)
MAYOR = "post-mayor"
MEMBER = "post-member"


def membership(post: str, **fields) -> Membership:
    return Membership(post_id=post, first_seen_at=_T, last_seen_at=_LATER, **fields)


@pytest.mark.unit
def test_a_person_with_no_membership_writes_no_row():
    assert membership_rows([Person(id="alice")]) == []


@pytest.mark.unit
def test_one_row_per_membership_keyed_by_person_and_post():
    alice = Person(id="alice", memberships=(membership(MAYOR), membership(MEMBER)))

    rows = membership_rows([alice])

    assert [row["id"] for row in rows] == [
        membership_id("alice", MAYOR),
        membership_id("alice", MEMBER),
    ]
    assert {row["person_id"] for row in rows} == {"alice"}
    assert [row["post_id"] for row in rows] == [MAYOR, MEMBER]


@pytest.mark.unit
def test_a_row_carries_every_column_the_fold_derived():
    alice = Person(
        id="alice",
        memberships=(
            membership(
                MAYOR,
                label="Mayor Pro Tem",
                start_date="2024-01-01",
                end_date="2028-01-01",
                designations=("Place 3",),
                unmatched_text=("Harbor Commissioner",),
                sources=(MembershipSource(note="Mayor", url="https://example.gov"),),
            ),
        ),
    )

    [row] = membership_rows([alice])

    assert row["label"] == "Mayor Pro Tem"
    assert row["start_date"] == "2024-01-01"
    assert row["end_date"] == "2028-01-01"
    assert row["first_seen_at"] == _T
    assert row["last_seen_at"] == _LATER
    assert row["designations"] == ["Place 3"]
    assert row["meta_unmatched_text"] == ["Harbor Commissioner"]
    assert json.loads(row["sources"]) == [{"note": "Mayor", "url": "https://example.gov"}]


@pytest.mark.unit
def test_each_extra_role_is_a_row_on_its_membership():
    alice = Person(
        id="alice",
        memberships=(membership(MAYOR, extra_roles=("council-member", "board-member")),),
    )

    assert membership_role_rows([alice]) == [
        (membership_id("alice", MAYOR), "council-member"),
        (membership_id("alice", MAYOR), "board-member"),
    ]


@pytest.mark.unit
def test_a_membership_with_no_extra_roles_writes_no_role_row():
    assert membership_role_rows([Person(id="alice", memberships=(membership(MAYOR),))]) == []
