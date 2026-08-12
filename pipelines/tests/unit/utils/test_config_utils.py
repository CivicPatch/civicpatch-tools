import pytest
from unittest.mock import patch
from shared.schemas import RoleConfig, Role
from shared.utils.config_utils import get_role_alias_map

pytestmark = pytest.mark.unit


@patch('shared.utils.config_utils.get_role_configs')
def test_get_role_alias_map_basic(mock_get_role_configs):
    mock_get_role_configs.return_value = [
        Role(label="Mayor", aliases=["Head of City", "City Leader"]),
        Role(label="Council Member", aliases=["CM", "Board Member"]),
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
        Role(label="Mayor", aliases=["Head of City"]),
    ]
    result = get_role_alias_map()
    assert result["mayor"] == "Mayor"
    assert result["head of city"] == "Mayor"
