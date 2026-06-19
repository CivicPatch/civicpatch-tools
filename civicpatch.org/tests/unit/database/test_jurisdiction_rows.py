"""Unit tests for jurisdiction_rows — shapes parsed jurisdiction entries (the list under
the `jurisdictions:` key of a jurisdictions.yml) into the rows bulk_update_jurisdictions stores:

    (jurisdiction_ocdid, state, level, <entry serialized as JSON>, updated_at)

state and level come from the file's PATH (data_source/<state>/<level>/jurisdictions.yml);
updated_at is passed in (the sync stamps now()). Both are the same for every row in a call —
unlike people_rows, where each person carried its own jurisdiction_ocdid. Pure function.
"""

import json

import pytest
from database.jurisdictions import jurisdiction_rows

_ENTRY = {
    "id": "ocd-jurisdiction/country:us/state:tx/place:houston/government",
    "name": "Houston city",
    "url": "https://www.houstontx.gov/",
    "population": 2300419,
    "geoid": "4835000",
}
_ENTRY_2 = {
    "id": "ocd-jurisdiction/country:us/state:tx/place:dallas/government",
    "name": "Dallas city",
    "url": "https://www.dallascityhall.com/",
    "population": 1299553,
    "geoid": "4819000",
}
_UPDATED_AT = "2026-06-18T00:00:00+00:00"


@pytest.mark.unit
def test_one_entry_returns_one_row():
    rows = jurisdiction_rows([_ENTRY], "tx", "local", _UPDATED_AT)
    assert len(rows) == 1
    ocdid, _state, _level, _data, updated_at = rows[0]
    assert ocdid == _ENTRY["id"]
    assert updated_at == _UPDATED_AT


@pytest.mark.unit
def test_state_and_level_arg_returns_in_row():
    rows = jurisdiction_rows([_ENTRY], "tx", "local", _UPDATED_AT)
    _ocdid, state, level, _data, _updated = rows[0]
    assert state == "tx"  # from the arg, not the entry (the entry has no state/level)
    assert level == "local"


@pytest.mark.unit
def test_entry_returns_row():
    # the data column holds the whole entry, serialized losslessly (round-trip)
    rows = jurisdiction_rows([_ENTRY], "tx", "local", _UPDATED_AT)
    assert json.loads(rows[0][3]) == _ENTRY


@pytest.mark.unit
def test_multiple_entries_returns_multiple_rows():
    rows = jurisdiction_rows([_ENTRY, _ENTRY_2], "tx", "local", _UPDATED_AT)
    assert len(rows) == 2
    assert [row[0] for row in rows] == [_ENTRY["id"], _ENTRY_2["id"]]  # order preserved


@pytest.mark.unit
def test_empty_entries_returns_empty_list():
    assert jurisdiction_rows([], "tx", "local", _UPDATED_AT) == []
