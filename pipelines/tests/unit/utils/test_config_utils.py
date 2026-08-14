import pytest
from unittest.mock import patch
from shared.schemas import RoleConfig, Role, RoleStatus
from shared.utils.config_utils import get_role_alias_map, get_role_configs

pytestmark = pytest.mark.unit


# ── get_role_configs: the one place that decides what the matcher sees ──


def _role(label: str, status: RoleStatus) -> Role:
    return Role(id=label.lower().replace(" ", "-"), label=label, status=status)


def test_get_role_configs_keeps_only_active():
    config = RoleConfig(roles=[
        _role("Mayor", RoleStatus.ACTIVE),
        _role("Webmaster", RoleStatus.EXCLUDED),
        _role("Alderman", RoleStatus.INACTIVE),
        _role("Dogcatcher", RoleStatus.CANDIDATE),
    ])
    assert [r.label for r in get_role_configs(config)] == ["Mayor"]


def test_get_role_configs_no_override_is_empty():
    assert get_role_configs(None) == []


@patch('shared.utils.config_utils.get_role_configs')
def test_get_role_alias_map_basic(mock_get_role_configs):
    mock_get_role_configs.return_value = [
        Role(id="mayor", label="Mayor", aliases=["Head of City", "City Leader"]),
        Role(id="council-member", label="Council Member", aliases=["CM", "Board Member"]),
    ]
    result = get_role_alias_map()
    assert result == {
        "mayor": "Mayor",
        "head of city": "Mayor",
        "city leader": "Mayor",
        "council member": "Council Member",
        "cm": "Council Member",
        "board member": "Council Member",
    }


@patch('shared.utils.config_utils.get_role_configs')
def test_get_role_alias_map_empty(mock_get_role_configs):
    mock_get_role_configs.return_value = []
    assert get_role_alias_map() == {}


@patch('shared.utils.config_utils.get_role_configs')
def test_get_role_alias_map_case_insensitive(mock_get_role_configs):
    mock_get_role_configs.return_value = [
        Role(id="mayor", label="Mayor", aliases=["Head of City"]),
    ]
    result = get_role_alias_map()
    assert result["mayor"] == "Mayor"
    assert result["head of city"] == "Mayor"
