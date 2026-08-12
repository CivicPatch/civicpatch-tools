import pytest
from domain.models import Person
from shared.schemas import RoleConfig, Role
from utils import taxonomy as taxonomy
from utils.people_utils import sort_people
from utils.taxonomy import Taxonomy

pytestmark = pytest.mark.unit

EMPTY = taxonomy.build_taxonomy(RoleConfig(roles=[]))

_MAYOR_COUNCIL = taxonomy.build_taxonomy(
    RoleConfig(roles=[Role(label="Mayor"), Role(label="Council Member")])
)

_VICE_CHAIR = taxonomy.build_taxonomy(
    RoleConfig(
        roles=[
            Role(
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

_SELECT_BOARD = taxonomy.build_taxonomy(
    RoleConfig(
        roles=[
            Role(
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

# Keys are stored in lookup form, so "at-large" is keyed "at large".
_SORT_TAXONOMY = Taxonomy(
    role_aliases={},
    designation_aliases={"seat": "seat", "ward": "ward", "at large": "at-large"},
    role_priority={"Mayor": 0, "Council": 1, "Seat": 2},
    designation_priority={"seat": 0, "ward": 1, "at large": 2},
)


def _person(name: str, roles: list[str], designations: list[str]) -> Person:
    return Person(
        name=name,
        roles=roles,
        designations=designations,
        updated_at="2024-01-01",
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc",
        source_urls=[],
    )


# --- normalize_roles ---


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
    assert taxonomy.normalize_roles(roles, EMPTY) == expected


def test_normalize_roles_unknown_role_is_kept():
    assert taxonomy.normalize_roles(["Parks Liaison"], EMPTY) == ["Parks Liaison"]


def test_normalize_roles_config_order_is_respected():
    result = taxonomy.normalize_roles(["Council Member", "Mayor"], _MAYOR_COUNCIL)
    assert result == ["Mayor", "Council Member"]


def test_normalize_roles_splits_on_slash():
    result = taxonomy.normalize_roles(["Mayor/Council Member"], _MAYOR_COUNCIL)
    assert result == ["Mayor", "Council Member"]


def test_normalize_roles_hyphen_variant():
    assert taxonomy.normalize_roles(["vice-chair"], _VICE_CHAIR) == ["Vice Chair"]


def test_normalize_roles_hyphen_council_prefix():
    assert taxonomy.normalize_roles(["council vice-chair"], _VICE_CHAIR) == [
        "Vice Chair"
    ]


def test_normalize_roles_selectboard_fuzzy():
    assert taxonomy.normalize_roles(["selectboard vice chair"], _SELECT_BOARD) == [
        "Select Board Vice Chair"
    ]


# --- sort_people ---


def test_sort_people_priority_and_numeric():
    people = [
        _person("Alice", ["Council"], ["Ward 2"]),
        _person("Bob", ["Mayor"], ["At-Large"]),
        _person("Carol", ["Seat"], ["Seat 10"]),
        _person("Dave", ["Seat"], ["Seat 1"]),
        _person("Eve", ["Council"], ["Ward 1"]),
    ]
    sorted_people = sort_people(people, _SORT_TAXONOMY)
    assert [p.name for p in sorted_people] == ["Bob", "Eve", "Alice", "Dave", "Carol"]
