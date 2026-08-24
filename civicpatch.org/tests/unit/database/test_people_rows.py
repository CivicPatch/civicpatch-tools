"""Unit tests for people_rows — shapes a parsed people file (a list of person dicts) into the
rows bulk_update_people and publish store.

Named rows, not tuples, since 134: the whole person is still `data`, and the ten columns 134
split out ride alongside. Pure function — the DB layer owns its row format here, so this is a
plain unit test (no DB).
"""

import json

import pytest

from database.people import people_rows

_PERSON = {
    "id": "22aa-1",
    "name": "Kirk Watson",
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:tx/place:austin/government",
    "office": {"name": "Mayor", "division_ocdid": "ocd-division/country:us/state:tx/place:austin"},
    "phones": ["(512) 974-2250"],
    "updated_at": "2026-03-21T03:08:06+00:00",
}
_PERSON_2 = {
    "id": "edc6-2",
    "name": "Natasha Harper-Madison",
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:tx/place:austin/government",
    "office": {"name": "Council Member"},
    "updated_at": "2026-03-21T03:08:06+00:00",
}


@pytest.mark.unit
def test_one_person_returns_one_row():
    rows = people_rows([_PERSON])
    assert len(rows) == 1
    assert rows[0]["id"] == "22aa-1"
    assert rows[0]["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:tx/place:austin/government"
    assert rows[0]["updated_at"] == "2026-03-21T03:08:06+00:00"


@pytest.mark.unit
def test_multiple_people_returns_multiple_rows_each():
    rows = people_rows([_PERSON, _PERSON_2])
    assert len(rows) == 2
    assert [row["id"] for row in rows] == ["22aa-1", "edc6-2"]  # one row each, order preserved


@pytest.mark.unit
def test_data_column_holds_full_person():
    rows = people_rows([_PERSON])
    # round-trip: the data column is the whole person, serialized losslessly
    assert json.loads(rows[0]["data"]) == _PERSON


@pytest.mark.unit
def test_the_split_out_columns_carry_the_same_values():
    """134 duplicated ten fields out of the blob. Both halves are written, so a row where they
    disagree is a row where the reader you happen to pick decides the answer."""
    row = people_rows([_PERSON])[0]
    assert row["name"] == "Kirk Watson"
    assert row["phones"] == ["(512) 974-2250"]


@pytest.mark.unit
def test_a_missing_list_field_becomes_an_empty_array_not_null():
    """The columns are NOT NULL with a '{}' default, so None would be rejected outright — and
    a person with no emails has none, rather than an unknown number of them."""
    row = people_rows([_PERSON_2])[0]
    assert row["emails"] == []
    assert row["other_names"] == []
    # Scalars stay None: no image is genuinely unknown, and the column is nullable.
    assert row["image"] is None


@pytest.mark.unit
def test_office_is_not_a_column():
    """Role and division live on posts/memberships. A third copy would be a third answer."""
    assert "office" not in people_rows([_PERSON])[0]
