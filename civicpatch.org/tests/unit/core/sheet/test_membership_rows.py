"""What a membership looks like once it is a spreadsheet row.

Pure — no database and no Sheets. The risk this covers is the column *order* contract, and that
every key read here is the name `list_for_state` aliases its column to: a rename on one side
alone leaves the cell silently empty rather than raising.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.sheet.membership_rows import HEADERS, to_row, to_rows

_SHERBORN = (
    "ocd-jurisdiction/country:us/state:ma/county:middlesex/place:sherborn/government"
)
_SEEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
_LEFT_OFFICE = datetime(2027, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _membership(**overrides) -> dict:
    membership = {
        "jurisdiction_ocdid": _SHERBORN,
        "person_id": "person-1",
        "person_name": "Ana Reyes",
        "post_id": "post-1",
        "post_label": "Select Board Member",
        "post_role_id": "select-board-member",
        "post_division_ocdid": "ocd-division/country:us/state:ma/place:sherborn",
        "membership_id": "membership-1",
        "membership_label": "Select Board Chair",
        "membership_start_date": "2024",
        "membership_end_date": None,
        "membership_first_seen_at": _SEEN,
        "membership_last_seen_at": _SEEN,
        "membership_closed_at": None,
        "membership_source_labels": [],
    }
    membership.update(overrides)
    return membership


def _cell(row: list[str], column: str) -> str:
    return row[HEADERS.index(column)]


@pytest.mark.unit
def test_a_row_is_as_wide_as_the_header():
    """The header names positions, so a row of a different width transposes every column
    after the mismatch and nothing raises."""
    assert len(to_row(_membership())) == len(HEADERS)


@pytest.mark.unit
def test_an_open_membership_has_no_closed_at():
    """Empty is the whole signal that they still hold the seat — `closed_at` is nullable on
    `memberships` and nothing else records it."""
    assert _cell(to_row(_membership()), "membership_closed_at") == ""


@pytest.mark.unit
def test_a_closed_membership_carries_when_it_closed():
    """The distinction the sheet exists to show: git renders only the open half."""
    row = to_row(_membership(membership_closed_at=_LEFT_OFFICE))
    assert _cell(row, "membership_closed_at") == "2027-03-01T12:00:00+00:00"


@pytest.mark.unit
def test_the_membership_label_is_the_one_that_lands():
    """`label` on the row is the membership's; `post_label` is the seat's. Two different
    things, and the header keeps them apart."""
    row = to_row(_membership())
    assert _cell(row, "membership_label") == "Select Board Chair"
    assert _cell(row, "post_label") == "Select Board Member"


@pytest.mark.unit
def test_lists_join_on_a_pipe():
    row = to_row(_membership(membership_source_labels=["Chair", "Selectman"]))
    assert _cell(row, "membership_source_labels") == "Chair | Selectman"


@pytest.mark.unit
def test_a_timestamp_is_rendered_in_utc():
    """psycopg hands back whatever tz the column carries; the sheet shows one."""
    eastern = timezone(timedelta(hours=-5))
    row = to_row(
        _membership(membership_first_seen_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=eastern))
    )
    assert _cell(row, "membership_first_seen_at") == "2026-01-02T08:04:05+00:00"


@pytest.mark.unit
def test_nothing_set_is_empty_rather_than_none():
    """A `None` reaching a cell writes the literal "None", which reads as data."""
    row = to_row({})
    assert len(row) == len(HEADERS)
    assert set(row) == {""}


@pytest.mark.unit
def test_two_turns_in_a_seat_are_two_rows():
    """The history case: one person, one post, an earlier closed stint and a current one."""
    rows = to_rows(
        [
            _membership(membership_id="old", membership_closed_at=_LEFT_OFFICE),
            _membership(membership_id="current"),
        ]
    )
    assert [_cell(row, "membership_id") for row in rows] == ["old", "current"]
    assert [bool(_cell(row, "membership_closed_at")) for row in rows] == [True, False]
