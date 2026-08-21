import pytest
from shared.schemas import RoleConfig, Role
from shared.utils import taxonomy as taxonomy

pytestmark = pytest.mark.unit

EMPTY = taxonomy.build_taxonomy(RoleConfig(roles=[]))

_MAYOR_COUNCIL = taxonomy.build_taxonomy(
    RoleConfig(roles=[Role(id="mayor", label="Mayor"), Role(id="council-member", label="Council Member")])
)

_VICE_CHAIR = taxonomy.build_taxonomy(
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

_SELECT_BOARD = taxonomy.build_taxonomy(
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
