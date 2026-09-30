import pytest
from shared.schemas import Role, RoleConfig
from shared.utils.taxonomy import (
    Taxonomy,
    build_taxonomy,
    lookup_key,
    normalize_designations,
    normalize_roles,
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
        # Position abbreviations. "Posn. 2" is the case 2.1c was named for: "posn" and
        # "pos." were aliases but "posn." was neither, so the trailing period broke it.
        (["Posn. 2"], ["Position 2"]),
        (["Posn 2"], ["Position 2"]),
        (["Psn 5"], ["Position 5"]),
        (["Pos 3"], ["Position 3"]),
        (["Pos. 3"], ["Position 3"]),
        (["Position No. 4"], ["Position 4"]),
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


# --- normalize_roles ---


EMPTY = build_taxonomy(RoleConfig(roles=[]))

_MAYOR_COUNCIL = build_taxonomy(
    RoleConfig(roles=[Role(id="mayor", label="Mayor"), Role(id="council-member", label="Council Member")])
)

_VICE_CHAIR = build_taxonomy(
    RoleConfig(
        roles=[
            Role(
                id="vice-chair",
                label="Vice Chair",
                aliases=[
                    "council vice chair",
                    "council vice chairman",
                    "council vice chairwoman",
                    "vice chairman",
                    "vice chairwoman",
                ],
            ),
        ]
    )
)

_SELECT_BOARD = build_taxonomy(
    RoleConfig(
        roles=[
            Role(
                id="select-board-vice-chair",
                label="Select Board Vice Chair",
                aliases=[
                    "select board vice chairman",
                    "select board vice chairwoman",
                    "selectboard vice chair",
                    "selectboard vice chairman",
                    "selectboard vice chairwoman",
                ],
            ),
        ]
    )
)


@pytest.mark.parametrize(
    "roles, expected",
    [
        (
            ["Mayor", "mayor"],
            ["Mayor"],
        ),  # Case-insensitive dedup — keeps first occurrence
        ([], []),  # Empty input
        ([None, ""], []),  # Invalid roles
        (["  mayor  ", "MAYOR"], ["mayor"]),  # Mixed case — keeps first occurrence
        (["mayor"], ["mayor"]),  # Single unknown role preserves original casing
    ],
)
def test_normalize_roles(roles, expected):
    assert normalize_roles(roles, EMPTY) == expected


def test_normalize_roles_unknown_role_is_kept():
    assert normalize_roles(["Parks Liaison"], EMPTY) == ["Parks Liaison"]


def test_normalize_roles_config_order_is_respected():
    result = normalize_roles(["Council Member", "Mayor"], _MAYOR_COUNCIL)
    assert result == ["Mayor", "Council Member"]


def test_normalize_roles_splits_on_slash():
    result = normalize_roles(["Mayor/Council Member"], _MAYOR_COUNCIL)
    assert result == ["Mayor", "Council Member"]


def test_normalize_roles_hyphen_variant():
    assert normalize_roles(["vice-chair"], _VICE_CHAIR) == ["Vice Chair"]


def test_normalize_roles_hyphen_council_prefix():
    assert normalize_roles(["council vice-chair"], _VICE_CHAIR) == [
        "Vice Chair"
    ]


def test_normalize_roles_selectboard_fuzzy():
    assert normalize_roles(["selectboard vice chair"], _SELECT_BOARD) == [
        "Select Board Vice Chair"
    ]


def _shared_member_taxonomy(council_first: bool) -> Taxonomy:
    council = Role(id="council-member", label="Council Member", aliases=["member"])
    select_board = Role(id="select-board-member", label="Select Board Member", aliases=["member"])
    first, second = (council, select_board) if council_first else (select_board, council)
    return build_taxonomy(
        RoleConfig(roles=[first.model_copy(update={"priority": 0}), second.model_copy(update={"priority": 1})])
    )


def test_a_shared_alias_goes_to_the_higher_priority_role():
    assert resolve_role("member", _shared_member_taxonomy(council_first=True)) == "Council Member"
    assert resolve_role("member", _shared_member_taxonomy(council_first=False)) == "Select Board Member"


def test_a_label_always_names_its_own_role_whatever_the_priority():
    taxonomy = _shared_member_taxonomy(council_first=True)

    assert resolve_role("Select Board Member", taxonomy) == "Select Board Member"
