"""What a person looks like once it is a spreadsheet row.

Person-grained, which is the point of the tab: one row per person however many seats they have
held. Pure — no database and no Sheets.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.sheet.people_rows import HEADERS, to_row, to_rows

_SHERBORN = (
    "ocd-jurisdiction/country:us/state:ma/county:middlesex/place:sherborn/government"
)
_SEEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _person(**overrides) -> dict:
    person = {
        "jurisdiction_ocdid": _SHERBORN,
        "person_id": "person-1",
        "person_name": "Ana Reyes",
        "person_other_names": [],
        "person_emails": ["ana@sherbornma.org"],
        "person_phones": [],
        "person_urls": [],
        "person_image": None,
        "person_cdn_image": None,
        "person_source_urls": [],
        "person_updated_at": _SEEN,
    }
    person.update(overrides)
    return person


def _cell(row: list[str], column: str) -> str:
    return row[HEADERS.index(column)]


@pytest.mark.unit
def test_a_row_is_as_wide_as_the_header():
    assert len(to_row(_person())) == len(HEADERS)


@pytest.mark.unit
def test_no_membership_columns_leak_in():
    """The split's whole purpose. A membership column here would put the tab back at membership
    grain, and counting it would stop giving people."""
    assert not [name for name in HEADERS if name.startswith("membership_")]
    assert not [name for name in HEADERS if name.startswith("post_")]


@pytest.mark.unit
def test_lists_join_on_a_pipe():
    row = to_row(_person(person_emails=["a@x.org", "b@x.org"]))
    assert _cell(row, "person_emails") == "a@x.org | b@x.org"


@pytest.mark.unit
def test_the_promoted_photo_wins_when_there_is_one():
    row = to_row(
        _person(person_image="local://a.jpg", person_cdn_image="https://cdn/a.jpg")
    )
    assert _cell(row, "person_image") == "https://cdn/a.jpg"


@pytest.mark.unit
def test_an_unpromoted_photo_still_shows():
    row = to_row(_person(person_image="local://a.jpg"))
    assert _cell(row, "person_image") == "local://a.jpg"


@pytest.mark.unit
def test_a_timestamp_is_rendered_in_utc():
    eastern = timezone(timedelta(hours=-5))
    row = to_row(
        _person(person_updated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=eastern))
    )
    assert _cell(row, "person_updated_at") == "2026-01-02T08:04:05+00:00"


@pytest.mark.unit
def test_nothing_set_is_empty_rather_than_none():
    """A `None` reaching a cell writes the literal "None", which reads as data."""
    row = to_row({})
    assert len(row) == len(HEADERS)
    assert set(row) == {""}


@pytest.mark.unit
def test_each_person_is_one_row():
    assert len(to_rows([_person(person_id="a"), _person(person_id="b")])) == 2
