import pytest
from utils.designation_utils import sort_designations, designations_without_division, resolve_division, division_ocdid_to_designation
from utils import designation_utils

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("divisions, expected", [
    (["District 1"], ["District 1"]),
    (["Council District 3"], ["District 3"]),
    (["At-Large Position 8"], ["At-Large", "Position 8"]),
    (["Unknown Division"], ["Unknown Division"]),
    (["District 5, Position 8"], ["District 5", "Position 8"]),
    (["At-Large Position 8", "District 3"], ["At-Large", "Position 8", "District 3"]),
    (["North Ward", "Blue Ward"], ["Ward North", "Ward Blue"]),
    (["North Ward", "South Ward"], ["Ward North", "Ward South"]),
    (["North Ward", "Ward North"], ["Ward North"]),
    (["1st Ward", "2nd District"], ["Ward 1", "District 2"]),
    (["1st Ward", "Ward 1"], ["Ward 1"]),
    (["Ward 5 (Blue Forest)"], ["Ward 5"]),
    (["Ward 1 (North)", "Ward 1"], ["Ward 1"]),
    (["District IV", "Ward IX"], ["District 4", "Ward 9"]),
    (["District # 3"], ["District 3"]),
    (["District #3"], ["District 3"]),
    (["Ward First"], ["Ward 1"]),
    (["First Ward"], ["Ward 1"]),
    (["Seat 1 District 2"], ["District 2", "Seat 1"]),
    (["Place 3, District 2"], ["Place 3", "District 2"]),
    ([], []),
    ([None, ""], []),
])
def test_normalize_designations(divisions, expected):
    result = designation_utils.normalize_designations(divisions)
    if isinstance(expected, list) and len(expected) > 1:
        assert sorted(result) == sorted(expected)
    else:
        assert result == expected


def test_sort_designations_priority_and_numeric(monkeypatch):
    monkeypatch.setattr("utils.designation_utils.get_designation_priority", lambda: {"seat": 0, "ward": 1, "at-large": 2})
    designations = ["Ward 2", "Seat 10", "Seat 1", "At-Large", "Ward 1"]
    assert sort_designations(designations) == ["Seat 1", "Seat 10", "Ward 1", "Ward 2", "At-Large"]


def test_sort_designations_no_priority(monkeypatch):
    monkeypatch.setattr("utils.designation_utils.get_designation_priority", lambda: {})
    designations = ["Ward 2", "Ward 1", "Ward 10"]
    assert sort_designations(designations) == ["Ward 1", "Ward 2", "Ward 10"]


_MIXED_CONFIGS = {"district": {"has_geographic_area": True}, "at-large": {"has_geographic_area": False}}


@pytest.mark.parametrize("designations, expected", [
    (["district 1"],            []),
    (["District 3"],            []),
    (["at-large", "district 2"], ["at-large"]),
    (["at-large", "seat 1"],    ["at-large", "seat 1"]),
    (["district"],              ["district"]),   # no value → not geographic
    (["unknown 5"],             ["unknown 5"]),
    ([],                        []),
])
def test_designations_without_division(monkeypatch, designations, expected):
    monkeypatch.setattr("utils.designation_utils.config_utils.get_designations", lambda: _MIXED_CONFIGS)
    assert designations_without_division(designations) == expected


@pytest.mark.parametrize("jurisdiction_ocdid, designations, expected_division", [
    (
        "ocd-jurisdiction/country:us/state:xy/place:alpha/government",
        [],
        "ocd-division/country:us/state:xy/place:alpha",
    ),
    (
        "ocd-jurisdiction/country:us/state:xy/place:bravo/government",
        ["district 1"],
        "ocd-division/country:us/state:xy/place:bravo/council_district:1",
    ),
    (
        "ocd-jurisdiction/country:us/state:xy/place:echo/government",
        ["at-large", "district 2"],
        "ocd-division/country:us/state:xy/place:echo/council_district:2",
    ),
    (
        "ocd-jurisdiction/country:us/state:xy/place:charlie/government",
        ["district"],   # no value → falls back to base
        "ocd-division/country:us/state:xy/place:charlie",
    ),
])
def test_resolve_division(monkeypatch, jurisdiction_ocdid, designations, expected_division):
    monkeypatch.setattr("utils.designation_utils.config_utils.get_designations", lambda: _MIXED_CONFIGS)
    assert resolve_division(jurisdiction_ocdid, designations) == expected_division


_OCDID = "ocd-jurisdiction/country:us/state:tx/place:katy/government"
_DIVISION_BASE = "ocd-division/country:us/state:tx/place:katy"


@pytest.mark.parametrize("division_ocdid, expected", [
    # numeric ward
    (f"{_DIVISION_BASE}/ward:3",            ["Ward 3"]),
    # alphabetic ward (e.g. Katy TX)
    (f"{_DIVISION_BASE}/ward:a",            ["Ward A"]),
    (f"{_DIVISION_BASE}/ward:b",            ["Ward B"]),
    # council_district slug maps back to "district"
    (f"{_DIVISION_BASE}/council_district:5", ["District 5"]),
    # base division (at-large) → no designation
    (_DIVISION_BASE,                         []),
    # no division
    (None,                                   []),
])
def test_division_ocdid_to_designation(division_ocdid, expected):
    assert division_ocdid_to_designation(division_ocdid, _OCDID) == expected
