"""`membership_history`: rosters over time in, one row per period held out."""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import PostKey
from core.projection.membership_history import membership_history
from core.projection.people import Membership, Person
from core.projection.roster import Roster

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(days=30)
_T2 = _T0 + timedelta(days=60)
_COUNCIL = "11111111-1111-1111-1111-111111111111"
_BASE = "ocd-division/country:us/state:tx/place:alpha"
MAYOR = PostKey(organization_id=_COUNCIL, role_id="mayor", division_ocdid=_BASE)
MEMBER = PostKey(organization_id=_COUNCIL, role_id="council-member", division_ocdid=_BASE)


def _holding(post: PostKey, label: str | None = None) -> Roster:
    membership = Membership(post=post, opened_at=_T0, label=label)
    return Roster(people=(Person(id="jane", memberships=(membership,)),))


def _periods(rows) -> list[tuple[str, datetime, datetime | None]]:
    return [(row.membership.post.role_id, row.opened_at, row.closed_at) for row in rows]


@pytest.mark.unit
def test_jane_is_mayor_then_member_then_mayor_again_three_rows():
    rows = membership_history([(_T0, _holding(MAYOR)), (_T1, _holding(MEMBER)), (_T2, _holding(MAYOR))])

    assert _periods(rows) == [
        ("mayor", _T0, _T1),
        ("council-member", _T1, _T2),
        ("mayor", _T2, None),
    ]


@pytest.mark.unit
def test_a_membership_held_throughout_is_one_open_row():
    rows = membership_history([(_T0, _holding(MAYOR)), (_T1, _holding(MAYOR))])

    assert _periods(rows) == [("mayor", _T0, None)]


@pytest.mark.unit
def test_a_closed_row_keeps_what_it_was_when_last_held():
    rows = membership_history(
        [(_T0, _holding(MAYOR, "Mayor")), (_T1, _holding(MAYOR, "Acting Mayor")), (_T2, Roster())]
    )

    assert [(row.membership.label, row.closed_at) for row in rows] == [("Acting Mayor", _T2)]


@pytest.mark.unit
def test_snapshots_sharing_a_moment_collapse_to_the_last():
    """A pair dropped and re-listed at one moment would otherwise open twice at the same time,
    which the row key (id, opened_at) cannot hold."""
    rows = membership_history(
        [(_T0, _holding(MAYOR)), (_T1, Roster()), (_T1, _holding(MAYOR))]
    )

    assert _periods(rows) == [("mayor", _T0, None)]
