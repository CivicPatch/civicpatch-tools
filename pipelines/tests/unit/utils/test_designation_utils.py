import pytest
from utils.designation_utils import sort_designations, extract_role_names_and_division_from_designations
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


@pytest.mark.parametrize(
    "designation_configs,jurisdiction_ocdid,office_designations,expected_role_names,expected_division",
    [
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:alpha/government",
            [], [],
            "ocd-division/country:us/state:xy/place:alpha"
        ),
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:bravo/government",
            ["district 1"], [],
            "ocd-division/country:us/state:xy/place:bravo/council_district:1"
        ),
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:charlie/government",
            ["district"], ["district"],
            "ocd-division/country:us/state:xy/place:charlie"
        ),
        (
            {"at-large": {"has_geographic_area": False}},
            "ocd-jurisdiction/country:us/state:xy/place:delta/government",
            ["at-large"], ["at-large"],
            "ocd-division/country:us/state:xy/place:delta"
        ),
        (
            {"district": {"has_geographic_area": True}, "at-large": {"has_geographic_area": False}},
            "ocd-jurisdiction/country:us/state:xy/place:echo/government",
            ["at-large", "district 2"], ["at-large"],
            "ocd-division/country:us/state:xy/place:echo/council_district:2"
        ),
        (
            {"at-large": {"has_geographic_area": False}, "seat": {"has_geographic_area": False}},
            "ocd-jurisdiction/country:us/state:xy/place:foxtrot/government",
            ["at-large", "seat 1"], ["at-large", "seat 1"],
            "ocd-division/country:us/state:xy/place:foxtrot"
        ),
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:golf/government",
            ["unknown 5"], ["unknown 5"],
            "ocd-division/country:us/state:xy/place:golf"
        ),
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:hotel/government",
            ["District 3"], [],
            "ocd-division/country:us/state:xy/place:hotel/council_district:3"
        ),
        (
            {},
            "ocd-jurisdiction/country:us/state:xy/place:india/government",
            ["1"], ["1"],
            "ocd-division/country:us/state:xy/place:india"
        ),
    ]
)
def test_extract_role_names_and_division_from_designations(
    designation_configs, jurisdiction_ocdid, office_designations, expected_role_names, expected_division
):
    role_names, division = extract_role_names_and_division_from_designations(
        designation_configs, jurisdiction_ocdid, office_designations
    )
    assert role_names == expected_role_names
    assert division == expected_division
