"""`membership_rows`: membership history as the rows the writer inserts.

This file also tested `membership_role_rows`; `membership_roles` was dropped (226), so those
two tests went with it. The rest now take history rows rather than a roster, because a row is
a period held, and one membership can have several.
"""

import json
from datetime import datetime, timezone

import pytest
from shared.utils.membership_ids import membership_id

from core.projection.membership_details import MembershipSource
from core.projection.facts import PostKey
from core.projection.membership_history import MembershipRow
from core.projection.people import Membership
from database.projection import membership_rows

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
_LATER = datetime(2026, 6, 1, tzinfo=timezone.utc)
COUNCIL = "11111111-1111-1111-1111-111111111111"
BASE = "ocd-division/country:us/state:tx/place:alpha"
MAYOR = PostKey(organization_id=COUNCIL, role_id="mayor", division_ocdid=BASE)
MEMBER = PostKey(
    organization_id=COUNCIL, role_id="council-member", division_ocdid=BASE
)


def row(post: PostKey, closed_at: datetime | None = None, **fields) -> MembershipRow:
    return MembershipRow(
        person_id="alice",
        membership=Membership(post=post, opened_at=_T, **fields),
        opened_at=_T,
        closed_at=closed_at,
    )


@pytest.mark.unit
def test_no_history_writes_no_row():
    assert membership_rows([]) == []


@pytest.mark.unit
def test_every_row_of_a_membership_shares_its_id():
    """The id is the pair claims are filed against; the period is what tells rows apart."""
    rows = membership_rows([row(MAYOR, closed_at=_LATER), row(MAYOR), row(MEMBER)])

    assert [r["id"] for r in rows] == [
        membership_id("alice", MAYOR.post_id),
        membership_id("alice", MAYOR.post_id),
        membership_id("alice", MEMBER.post_id),
    ]
    assert [r["closed_at"] for r in rows] == [_LATER, None, None]


@pytest.mark.unit
def test_a_row_carries_every_column_the_fold_derived():
    [written] = membership_rows(
        [
            row(
                MAYOR,
                label="Mayor Pro Tem",
                start_date="2024-01-01",
                end_date="2028-01-01",
                designations=("Place 3",),
                unmatched_text=("Harbor Commissioner",),
                sources=(MembershipSource(note="Mayor", url="https://example.gov"),),
            )
        ]
    )

    assert written["label"] == "Mayor Pro Tem"
    assert written["start_date"] == "2024-01-01"
    assert written["end_date"] == "2028-01-01"
    assert written["opened_at"] == _T
    assert written["designations"] == ["Place 3"]
    assert written["meta_unmatched_text"] == ["Harbor Commissioner"]
    assert json.loads(written["sources"]) == [{"note": "Mayor", "url": "https://example.gov"}]
