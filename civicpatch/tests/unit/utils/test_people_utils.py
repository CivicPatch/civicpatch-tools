import pytest
import logging
from utils import people_utils
from domain.models import Person
from utils.people_utils import sort_roles, sort_designations, sort_people, extract_role_names_and_division_from_designations

pytestmark = pytest.mark.unit

# Create dummy logger for testing
logger = logging.getLogger(__name__)


@pytest.mark.parametrize("roles, expected", [
    (["Mayor", "mayor"], ["Mayor"]),  # Case-insensitive deduplication
    (["Mayor", "Chief Executive"], ["Mayor"]),  # Alias normalization
    ([], []),  # Empty input
    ([None, ""], []),  # Invalid roles
    (["  mayor  ", "MAYOR"], ["Mayor"]),  # Mixed case and whitespace
])
def test_normalize_roles(roles, expected):
    assert people_utils.normalize_roles(logger, roles) == expected


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
    (["Seat 1 District 2"], ["District 2", "Seat 1"]),
    (["Place 3, District 2"], ["Place 3", "District 2"]),
    
    # Edge cases
    ([], []),  # Empty input
    ([None, ""], []),  # Invalid divisions
])
def test_normalize_designations(divisions, expected):
    result = people_utils.normalize_designations(divisions)
    if isinstance(expected, list) and len(expected) > 1:
        assert sorted(result) == sorted(expected)
    else:
        assert result == expected

def test_sort_roles_priority_and_numeric(monkeypatch):
    # Patch config priorities
    monkeypatch.setattr("utils.people_utils.get_role_priority", lambda: {"mayor": 0, "council": 1, "seat": 2})
    monkeypatch.setattr("utils.people_utils.get_designation_priority", lambda: {"seat": 0, "ward": 1})

    roles = ["Council", "Mayor", "Seat 10", "Seat 2", "Seat 1", "Ward 3"]
    # Should sort: Mayor (priority 0), Council (1), Seat 1 (2, num 1), Seat 2 (2, num 2), Seat 10 (2, num 10), Ward 3 (fallback)
    assert sort_roles(roles) == ["Mayor", "Council", "Seat 1", "Seat 2", "Seat 10", "Ward 3"]

def test_sort_designations_priority_and_numeric(monkeypatch):
    monkeypatch.setattr("utils.people_utils.get_designation_priority", lambda: {"seat": 0, "ward": 1, "at-large": 2})

    designations = ["Ward 2", "Seat 10", "Seat 1", "At-Large", "Ward 1"]
    # Should sort: Seat 1, Seat 10, Ward 1, Ward 2, At-Large
    assert sort_designations(designations) == ["Seat 1", "Seat 10", "Ward 1", "Ward 2", "At-Large"]

def test_sort_people_priority_and_numeric(monkeypatch):
    monkeypatch.setattr("utils.people_utils.get_role_priority", lambda: {"mayor": 0, "council": 1, "seat": 2})
    monkeypatch.setattr("utils.people_utils.get_designation_priority", lambda: {"seat": 0, "ward": 1, "at-large": 2})

    people = [
        Person(name="Alice", roles=["Council"], designations=["Ward 2"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
        Person(name="Bob", roles=["Mayor"], designations=["At-Large"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
        Person(name="Carol", roles=["Seat"], designations=["Seat 10"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
        Person(name="Dave", roles=["Seat"], designations=["Seat 1"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
        Person(name="Eve", roles=["Council"], designations=["Ward 1"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
    ]
    # Should sort: Bob (Mayor), Eve (Council, Ward 1), Alice (Council, Ward 2), Dave (Seat, Seat 1), Carol (Seat, Seat 10)
    sorted_people = sort_people(people)
    assert [p.name for p in sorted_people] == ["Bob", "Eve", "Alice", "Dave", "Carol"]

def test_sort_roles_no_priority(monkeypatch):
    monkeypatch.setattr("utils.people_utils.get_role_priority", lambda: {})
    monkeypatch.setattr("utils.people_utils.get_designation_priority", lambda: {})
    roles = ["Seat 2", "Seat 1", "Seat 10"]
    assert sort_roles(roles) == ["Seat 1", "Seat 2", "Seat 10"]

def test_sort_designations_no_priority(monkeypatch):
    monkeypatch.setattr("utils.people_utils.get_designation_priority", lambda: {})
    designations = ["Ward 2", "Ward 1", "Ward 10"]
    assert sort_designations(designations) == ["Ward 1", "Ward 2", "Ward 10"]

@pytest.mark.parametrize(
    "designation_configs,jurisdiction_ocdid,office_designations,expected_role_names,expected_division",
    [
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:alpha/government",
            [],
            [],
            "ocd-division/country:us/state:xy/place:alpha"
        ),
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:bravo/government",
            ["district 1"],
            [],
            "ocd-division/country:us/state:xy/place:bravo/district:1"
        ),
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:charlie/government",
            ["district"],
            ["district"],
            "ocd-division/country:us/state:xy/place:charlie"
        ),
        (
            {"at-large": {"has_geographic_area": False}},
            "ocd-jurisdiction/country:us/state:xy/place:delta/government",
            ["at-large"],
            ["at-large"],
            "ocd-division/country:us/state:xy/place:delta"
        ),
        (
            {
                "district": {"has_geographic_area": True},
                "at-large": {"has_geographic_area": False}
            },
            "ocd-jurisdiction/country:us/state:xy/place:echo/government",
            ["at-large", "district 2"],
            ["at-large"],
            "ocd-division/country:us/state:xy/place:echo/district:2"
        ),
        (
            {
                "at-large": {"has_geographic_area": False},
                "seat": {"has_geographic_area": False}
            },
            "ocd-jurisdiction/country:us/state:xy/place:foxtrot/government",
            ["at-large", "seat 1"],
            ["at-large", "seat 1"],
            "ocd-division/country:us/state:xy/place:foxtrot"
        ),
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:golf/government",
            ["unknown 5"],
            ["unknown 5"],
            "ocd-division/country:us/state:xy/place:golf"
        ),
        (
            {"district": {"has_geographic_area": True}},
            "ocd-jurisdiction/country:us/state:xy/place:hotel/government",
            ["District 3"],
            [],
            "ocd-division/country:us/state:xy/place:hotel/district:3"
        ),
        (
            {},
            "ocd-jurisdiction/country:us/state:xy/place:india/government",
            ["1"],
            ["1"],
            "ocd-division/country:us/state:xy/place:india"
        )
    ]
)
def test_extract_role_names_and_division_from_designations(
    designation_configs, jurisdiction_ocdid, office_designations, expected_role_names, expected_division
):
    role_names, division = extract_role_names_and_division_from_designations(
        designation_configs, jurisdiction_ocdid, office_designations
    )
    assert role_names == expected_role_names
    assert division == expected_division