"""Unit tests for people_rows — shapes a parsed people file (a list of person dicts) into
the row tuples bulk_update_people stores:

    (id, jurisdiction_ocdid, <person serialized as JSON>, updated_at)

Each person dict carries its own id, jurisdiction_ocdid, and updated_at; the *whole* person
dict becomes the `data` (jsonb) column, serialized with json.dumps. Pure function — the DB
layer owns its row format here, so this is a plain unit test (no DB).
"""

import json

import pytest

from database.people import people_rows

_PERSON = {
    "id": "22aa-1",
    "name": "Kirk Watson",
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:tx/place:austin/government",
    "office": {"name": "Mayor", "division_ocdid": "ocd-division/country:us/state:tx/place:austin"},
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
    id_, ocdid, _data, updated_at = rows[0]
    assert id_ == "22aa-1"
    assert ocdid == "ocd-jurisdiction/country:us/state:tx/place:austin/government"
    assert updated_at == "2026-03-21T03:08:06+00:00"


@pytest.mark.unit
def test_multiple_people_returns_multiple_rows_each():
    rows = people_rows([_PERSON, _PERSON_2])
    assert len(rows) == 2
    assert [row[0] for row in rows] == ["22aa-1", "edc6-2"]  # one row each, order preserved


@pytest.mark.unit
def test_data_column_holds_full_person():
    rows = people_rows([_PERSON])
    data = rows[0][2]
    # round-trip: the data column is the whole person, serialized losslessly
    assert json.loads(data) == _PERSON
