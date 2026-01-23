import pytest
import logging
from utils import people_utils

pytestmark = pytest.mark.unit

# Create dummy logger and government_type for testing
logger = logging.getLogger(__name__)
government_type = "mayor_council"


@pytest.mark.parametrize("roles, expected", [
    (["Mayor", "mayor"], ["Mayor"]),  # Case-insensitive deduplication
    (["Mayor", "Chief Executive"], ["Mayor"]),  # Alias normalization
    ([], []),  # Empty input
    ([None, ""], []),  # Invalid roles
    (["  mayor  ", "MAYOR"], ["Mayor"]),  # Mixed case and whitespace
])
def test_normalize_roles(roles, expected):
    assert people_utils.normalize_roles(logger, government_type, roles) == expected


@pytest.mark.parametrize("divisions, expected", [
    # Basic single division tests
    (["District 1"], ["District 1"]),  # Single word division
    
    # Compound division tests
    (["Council District 3"], ["District 3"]),  # Compound division
    
    # At-large position tests
    (["At-Large Position 8"], ["At-Large", "Position 8"]),  # At-large position
    
    # Unknown division tests
    (["Unknown Division"], ["Unknown Division"]),  # Unknown division
    
    # Multiple division patterns
    (["District 5, Position 8"], ["District 5", "Position 8"]),  # District and position
    (["At-Large Position 8", "District 3"], ["At-Large", "Position 8", "District 3"]),  # Multiple divisions
    
    # Directional tests
    (["North Ward", "Blue Ward"], ["Ward North", "Ward Blue"]),  # Directions
    (["North Ward", "South Ward"], ["Ward North", "Ward South"]),  # Directional divisions
    (["North Ward", "Ward North"], ["Ward North"]),  # Alias normalization
    
    # Ordinal tests
    (["1st Ward", "2nd District"], ["Ward 1", "District 2"]),  # Ordinal
    (["1st Ward", "Ward 1"], ["Ward 1"]),  # Normalize ordinals
    
    # Parenthetical content tests
    (["Ward 5 (Blue Forest)"], ["Ward 5"]),  # Junk removal
    (["Ward 1 (North)", "Ward 1"], ["Ward 1"]),  # Remove parenthetical content
    
    # Roman numerals
    (["District IV", "Ward IX"], ["District 4", "Ward 9"]),  # Roman numerals
    
    # Hash symbol removal
    (["District # 3"], ["District 3"]),  # Remove hash symbol with space
    (["District #3"], ["District 3"]),  # Remove hash symbol without space

    (["Ward First"], ["Ward 1"]),  # Word to numeral conversion
    (["First Ward"], ["Ward 1"]),  # Word to numeral conversion alternative
    
    # Edge cases
    ([], []),  # Empty input
    ([None, ""], []),  # Invalid divisions
])
def test_normalize_divisions(divisions, expected):
    result = people_utils.normalize_divisions(divisions)
    if isinstance(expected, list) and len(expected) > 1:
        assert sorted(result) == sorted(expected)
    else:
        assert result == expected