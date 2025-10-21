import pytest
from unittest.mock import patch
from utils.config_utils import get_context_keywords, get_role_alias_map

pytestmark = pytest.mark.unit

@patch('utils.config_utils.get_role_configs_by_government_type')
def test_basic_functionality(mock_get_role_configs):
    mock_get_role_configs.return_value = [
        {"role": ["Mayor"], "aliases": ["Head of City", "City Leader"]},
        {"role": ["Council Member"], "aliases": ["CM", "Board Member"]}
    ]

    result = get_role_alias_map("mayor_council")
    expected = {
        "mayor": "Mayor",
        "head of city": "Mayor",
        "city leader": "Mayor",
        "council member": "Council Member",
        "cm": "Council Member",
        "board member": "Council Member"
    }
    assert result == expected

@patch('utils.config_utils.get_role_configs_by_government_type')
def test_empty_configuration(mock_get_role_configs):
    mock_get_role_configs.return_value = []

    result = get_role_alias_map("mayor_council")
    assert result == {}

@patch('utils.config_utils.get_role_configs_by_government_type')
def test_case_insensitivity(mock_get_role_configs):
    mock_get_role_configs.return_value = [
        {"role": ["Mayor"], "aliases": ["Head of City"]}
    ]

    result = get_role_alias_map("mayor_council")
    assert result["mayor"] == "Mayor"
    assert result["head of city"] == "Mayor"
    assert result["HEAD OF CITY".lower()] == "Mayor"

@patch('utils.config_utils.get_role_configs_by_government_type')
def test_multiple_aliases(mock_get_role_configs):
    mock_get_role_configs.return_value = [
        {"role": ["Mayor"], "aliases": ["Head of City", "City Leader", "Chief"]}
    ]

    result = get_role_alias_map("mayor_council")
    assert result["head of city"] == "Mayor"
    assert result["city leader"] == "Mayor"
    assert result["chief"] == "Mayor"

def test_get_context_keywords_mayor_council():
    keywords = get_context_keywords('mayor_council')
    # Check that some expected keywords are present (actual config-driven)
    assert 'mayor' in keywords
    assert 'position' in keywords
    # Check for some common aliases or related terms
    assert any(k in keywords for k in ['mayor'])
    assert any(k in keywords for k in ['city council'])
    # Ensure the result is not empty
    assert len(keywords) > 0
