import pytest
from shared.schemas import RoleConfig
from utils.taxonomy import (
    Taxonomy,
    build_taxonomy,
    lookup_key,
    normalize_designations,
    resolve_role,
    sort_designations,
)

_ROLE_ALIASES = {
    "select board vice chair": "Select Board Vice Chair",
    "selectboard vice chair": "Select Board Vice Chair",
    "vice chair": "Vice Chair",
    "council vice chair": "Vice Chair",
    "mayor": "Mayor",
    "deputy mayor": "Deputy Mayor",
    "chair": "Chair",
    "council president": "Council President",
    "deputy council president": "Deputy Council President",
}

_TAXONOMY = Taxonomy(
    role_aliases={
        lookup_key(alias): canonical for alias, canonical in _ROLE_ALIASES.items()
    },
    designation_aliases={},
    role_priority={},
    designation_priority={},
)


@pytest.mark.parametrize(
    "role,expected",
    [
        ("selectboard vice-chair", "Select Board Vice Chair"),
        ("select board vice-chair", "Select Board Vice Chair"),
        ("selectboard vice chair", "Select Board Vice Chair"),
    ],
)
def test_resolve_role_positive(role, expected):
    assert resolve_role(role, _TAXONOMY) == expected


@pytest.mark.parametrize(
    "role",
    [
        "parks liaison",
        "mayor elect",
        "board member",
        "city manager pro tem",
    ],
)
def test_resolve_role_negative_unknown(role):
    assert resolve_role(role, _TAXONOMY) is None


pytestmark = pytest.mark.unit


# --- normalize_designations ---

_DESIGNATIONS = build_taxonomy(RoleConfig(roles=[]))


@pytest.mark.parametrize(
    "divisions, expected",
    [
        (["District 1"], ["District 1"]),
        (["Council District 3"], ["District 3"]),
        (["At-Large Position 8"], ["At-Large", "Position 8"]),
        (["Unknown Division"], ["Unknown Division"]),
        (["District 5, Position 8"], ["District 5", "Position 8"]),
        (
            ["At-Large Position 8", "District 3"],
            ["At-Large", "Position 8", "District 3"],
        ),
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
    ],
)
def test_normalize_designations(divisions, expected):
    result = normalize_designations(divisions, _DESIGNATIONS)
    if isinstance(expected, list) and len(expected) > 1:
        assert sorted(result) == sorted(expected)
    else:
        assert result == expected


# --- sort_designations ---

# Keys are stored in lookup form, so "at-large" is keyed "at large".
_RANKED = Taxonomy(
    role_aliases={},
    designation_aliases={"seat": "seat", "ward": "ward", "at large": "at-large"},
    role_priority={},
    designation_priority={"seat": 0, "ward": 1, "at large": 2},
)

_UNRANKED = Taxonomy(
    role_aliases={},
    designation_aliases={"ward": "ward"},
    role_priority={},
    designation_priority={},
)


def test_sort_designations_priority_and_numeric():
    designations = ["Ward 2", "Seat 10", "Seat 1", "At-Large", "Ward 1"]
    assert sort_designations(designations, _RANKED) == [
        "Seat 1",
        "Seat 10",
        "Ward 1",
        "Ward 2",
        "At-Large",
    ]


def test_sort_designations_no_priority():
    designations = ["Ward 2", "Ward 1", "Ward 10"]
    assert sort_designations(designations, _UNRANKED) == ["Ward 1", "Ward 2", "Ward 10"]
