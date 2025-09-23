import pytest
from utils import people_utils

def test_single_word_division(self):
    result = people_utils.normalize_divisions(["District 1"])
    assert result == ["District 1"]

def test_compound_division(self):
    result = people_utils.normalize_divisions(["Council District 3"])
    assert result == ["District 3"]

def test_at_large_position(self):
    result = people_utils.normalize_divisions(["At-Large Position 8"])
    assert sorted(result) == sorted(["At-Large", "Position 8"])

def test_unknown_division(self):
    result = people_utils.normalize_divisions(["Unknown Division"])
    assert result == ["Unknown Division"]

def test_district_and_position(self):
    result = people_utils.normalize_divisions(["District 5, Position 8"])
    assert sorted(result) == sorted(["District 5", "Position 8"])

def test_ordinal(self):
    result = people_utils.normalize_divisions(["Ward 2nd"])
    assert result == ["Ward 2"]

def test_multiple_divisions(self):
    result = people_utils.normalize_divisions(["At-Large Position 8", "District 3"])
    assert sorted(result) == sorted(["At-Large", "Position 8", "District 3"])

def test_directions(self):
    result = people_utils.normalize_divisions(["Ward North", "District South"])
    assert sorted(result) == sorted(["Ward North", "District South"])

def test_directions(self):
    result = people_utils.normalize_divisions(["North Ward", "Blue Ward"])
    assert sorted(result) == sorted(["Ward North", "Ward Blue"])

def test_ordinal(self):
    result = people_utils.normalize_divisions(["1st Ward", "2nd District"])
    assert sorted(result) == sorted(["Ward 1", "District 2"])

def test_junk(self):
    result = people_utils.normalize_divisions(["Ward 5 (Blue Forest)"])
    assert sorted(result) == sorted(["Ward 5"])

def test_empty_divisions(self):
    result = people_utils.normalize_divisions([])
    assert result == []

def test_roman_numerals(self):
    result = people_utils.normalize_divisions(["District IV", "Ward IX"])
    assert sorted(result) == sorted(["District 4", "Ward 9"])


@pytest.mark.parametrize("roles, expected", [
    (["Mayor", "mayor"], ["Mayor"]),  # Case-insensitive deduplication
    (["Mayor", "Chief Executive"], ["Mayor"]),  # Alias normalization
    ([], []),  # Empty input
    ([None, ""], []),  # Invalid roles
    (["  mayor  ", "MAYOR"], ["Mayor"]),  # Mixed case and whitespace
])
def test_normalize_roles(roles, expected):
    assert people_utils.normalize_roles(roles) == expected


@pytest.mark.parametrize("divisions, expected", [
    (["1st Ward", "Ward 1"], ["Ward 1"]),  # Normalize ordinals
    (["North Ward", "Ward North"], ["Ward North"]),  # Alias normalization
    (["Ward 1 (North)", "Ward 1"], ["Ward 1"]),  # Remove parenthetical content
    (["North Ward", "South Ward"], ["Ward North", "Ward South"]),  # Directional divisions
    ([], []),  # Empty input
    ([None, ""], []),  # Invalid divisions
])
def test_normalize_divisions(divisions, expected):
    assert people_utils.normalize_divisions(divisions) == expected