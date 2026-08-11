import pytest
from utils.role_utils import fuzzy_match_role

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


@pytest.mark.parametrize(
    "role,expected",
    [
        ("selectboard vice-chair", "Select Board Vice Chair"),
        ("select board vice-chair", "Select Board Vice Chair"),
        ("selectboard vice chair", "Select Board Vice Chair"),
    ],
)
def test_fuzzy_match_role_positive(role, expected):
    assert fuzzy_match_role(role, _ROLE_ALIASES) == expected


@pytest.mark.parametrize(
    "role",
    [
        "parks liaison",
        "mayor elect",
        "board member",
        "city manager pro tem",
    ],
)
def test_fuzzy_match_role_negative_unknown(role):
    assert fuzzy_match_role(role, _ROLE_ALIASES) is None


pytestmark = pytest.mark.unit
