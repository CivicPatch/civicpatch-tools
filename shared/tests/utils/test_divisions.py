import pytest
from shared.utils.divisions import (
    designations_without_division,
    division_ocdid_to_designation,
    filter_divisions,
    resolve_division,
)


_MIXED_CONFIGS = {
    "district": {"is_division": True},
    "ward": {"is_division": True},
    "at-large": {"is_division": False},
}


@pytest.mark.parametrize(
    "designations, expected",
    [
        (["district 1"], []),
        (["District 3"], []),
        (["at-large", "district 2"], ["at-large"]),
        (["at-large", "seat 1"], ["at-large", "seat 1"]),
        (["district"], ["district"]),  # no value → not geographic
        (["unknown 5"], ["unknown 5"]),
        ([], []),
    ],
)
def test_designations_without_division(monkeypatch, designations, expected):
    monkeypatch.setattr(
        "shared.utils.divisions.config_utils.get_designations", lambda: _MIXED_CONFIGS
    )
    assert designations_without_division(designations) == expected


@pytest.mark.parametrize(
    "designations, expected",
    [
        (["district 1"], ["district 1"]),
        (["District 3"], ["district 3"]),
        (["district"], []),  # no value → not geographic
        (["at-large"], []),
        (["at-large", "district 2"], ["district 2"]),
        (["unknown 5"], []),
        ([], []),
    ],
)
def test_filter_divisions(monkeypatch, designations, expected):
    monkeypatch.setattr(
        "shared.utils.divisions.config_utils.get_designations", lambda: _MIXED_CONFIGS
    )
    assert filter_divisions(designations) == expected


@pytest.mark.parametrize(
    "designations",
    [
        ["district"],
        ["ward"],
        ["district 1"],
        ["at-large", "district 2", "seat 1"],
    ],
)
def test_the_two_division_predicates_partition_their_input(monkeypatch, designations):
    # A valueless geographic keyword ("district") used to land in both buckets.
    monkeypatch.setattr(
        "shared.utils.divisions.config_utils.get_designations", lambda: _MIXED_CONFIGS
    )
    geographic = {d.lower() for d in filter_divisions(designations)}
    non_geographic = {d.lower() for d in designations_without_division(designations)}
    assert not geographic & non_geographic
    assert geographic | non_geographic == {d.lower() for d in designations}


@pytest.mark.parametrize(
    "jurisdiction_ocdid, designations, expected_division",
    [
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
            ["district"],  # no value → falls back to base
            "ocd-division/country:us/state:xy/place:charlie",
        ),
        # council_district is the slug for a district at every level — a county's
        # commissioner district included.
        (
            "ocd-jurisdiction/country:us/state:xy/county:delta/government",
            ["district 3"],
            "ocd-division/country:us/state:xy/county:delta/council_district:3",
        ),
        (
            "ocd-jurisdiction/country:us/state:xy/county:delta/place:foxtrot/government",
            ["district 3"],
            "ocd-division/country:us/state:xy/county:delta/place:foxtrot/council_district:3",
        ),
        # ward is never renamed, at any level.
        (
            "ocd-jurisdiction/country:us/state:xy/county:delta/government",
            ["ward 2"],
            "ocd-division/country:us/state:xy/county:delta/ward:2",
        ),
    ],
)
def test_resolve_division(
    monkeypatch, jurisdiction_ocdid, designations, expected_division
):
    monkeypatch.setattr(
        "shared.utils.divisions.config_utils.get_designations", lambda: _MIXED_CONFIGS
    )
    assert resolve_division(jurisdiction_ocdid, designations) == expected_division


_OCDID = "ocd-jurisdiction/country:us/state:tx/place:katy/government"
_DIVISION_BASE = "ocd-division/country:us/state:tx/place:katy"


@pytest.mark.parametrize(
    "division_ocdid, expected",
    [
        # numeric ward
        (f"{_DIVISION_BASE}/ward:3", ["Ward 3"]),
        # alphabetic ward (e.g. Katy TX)
        (f"{_DIVISION_BASE}/ward:a", ["Ward A"]),
        (f"{_DIVISION_BASE}/ward:b", ["Ward B"]),
        # council_district slug maps back to "district"
        (f"{_DIVISION_BASE}/council_district:5", ["District 5"]),
        # base division (at-large) → no designation
        (_DIVISION_BASE, []),
        # no division
        (None, []),
    ],
)
def test_division_ocdid_to_designation(division_ocdid, expected):
    assert division_ocdid_to_designation(division_ocdid, _OCDID) == expected
