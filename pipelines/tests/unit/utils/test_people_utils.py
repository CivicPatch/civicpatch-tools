import pytest
from utils import people_utils
from domain.models import Person
from utils.people_utils import sort_roles, sort_people
from shared.utils.config_utils import RoleConfig, RoleEntry

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("roles, expected", [
    (["Mayor", "mayor"], ["Mayor"]),  # Case-insensitive dedup — keeps first occurrence
    ([], []),  # Empty input
    ([None, ""], []),  # Invalid roles
    (["  mayor  ", "MAYOR"], ["mayor"]),  # Mixed case — keeps first occurrence
    (["mayor"], ["mayor"]),  # Single unknown role preserves original casing
])
def test_normalize_roles(roles, expected):
    assert people_utils.normalize_roles(roles) == expected


_EXCLUDED_ROLE_CONFIG = RoleConfig(roles=[
    RoleEntry(role="city attorney", include=False, aliases=["municipal attorney", "town attorney", "village attorney", "city solicitor"]),
    RoleEntry(role="city secretary", include=False),
])


def test_normalize_roles_excluded_role_is_dropped():
    assert people_utils.normalize_roles(["City Attorney"], role_config=_EXCLUDED_ROLE_CONFIG) == []

def test_normalize_roles_excluded_alias_is_dropped():
    assert people_utils.normalize_roles(["Municipal Attorney"], role_config=_EXCLUDED_ROLE_CONFIG) == []

def test_normalize_roles_unknown_role_is_kept():
    assert people_utils.normalize_roles(["Parks Liaison"]) == ["Parks Liaison"]

def test_normalize_roles_config_order_is_respected():
    config = RoleConfig(roles=[RoleEntry(role="Mayor"), RoleEntry(role="Council Member")])
    result = people_utils.normalize_roles(["Council Member", "Mayor"], role_config=config)
    assert result == ["Mayor", "Council Member"]

def test_normalize_roles_excluded_role_removed_from_mix():
    mayor_config = RoleConfig(roles=[
        RoleEntry(role="Mayor"),
        RoleEntry(role="city secretary", include=False),
    ])
    assert people_utils.normalize_roles(["Mayor", "City Secretary"], role_config=mayor_config) == ["Mayor"]

def test_normalize_roles_slash_excluded():
    city_admin_config = RoleConfig(roles=[RoleEntry(role="city administrator", include=False)])
    assert people_utils.normalize_roles(["Mayor/City Administrator"], role_config=city_admin_config) == ["Mayor"]


_VICE_CHAIR_CONFIG = RoleConfig(roles=[
    RoleEntry(role="Vice Chair", aliases=["council vice chair", "council vice chairman", "council vice chairwoman", "vice chairman", "vice chairwoman"]),
])

_SELECT_BOARD_CONFIG = RoleConfig(roles=[
    RoleEntry(role="Select Board Vice Chair", aliases=["select board vice chairman", "select board vice chairwoman", "selectboard vice chair", "selectboard vice chairman", "selectboard vice chairwoman"]),
])


def test_normalize_roles_hyphen_variant():
    assert people_utils.normalize_roles(["vice-chair"], role_config=_VICE_CHAIR_CONFIG) == ["Vice Chair"]

def test_normalize_roles_hyphen_council_prefix():
    assert people_utils.normalize_roles(["council vice-chair"], role_config=_VICE_CHAIR_CONFIG) == ["Vice Chair"]

def test_normalize_roles_selectboard_fuzzy():
    assert people_utils.normalize_roles(["selectboard vice chair"], role_config=_SELECT_BOARD_CONFIG) == ["Select Board Vice Chair"]

def test_normalize_roles_unknown_unchanged():
    assert people_utils.normalize_roles(["Parks Liaison"]) == ["Parks Liaison"]


def test_sort_roles_priority_and_numeric(monkeypatch):
    monkeypatch.setattr("utils.people_utils.get_role_priority", lambda *_: {"mayor": 0, "council": 1, "seat": 2})
    monkeypatch.setattr("utils.people_utils.get_designation_priority", lambda: {"seat": 0, "ward": 1})
    roles = ["Council", "Mayor", "Seat 10", "Seat 2", "Seat 1", "Ward 3"]
    assert sort_roles(roles) == ["Mayor", "Council", "Seat 1", "Seat 2", "Seat 10", "Ward 3"]

def test_sort_people_priority_and_numeric(monkeypatch):
    monkeypatch.setattr("utils.people_utils.get_role_priority", lambda *_: {"mayor": 0, "council": 1, "seat": 2})
    monkeypatch.setattr("utils.people_utils.get_designation_priority", lambda: {"seat": 0, "ward": 1, "at-large": 2})
    people = [
        Person(name="Alice", roles=["Council"], designations=["Ward 2"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
        Person(name="Bob", roles=["Mayor"], designations=["At-Large"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
        Person(name="Carol", roles=["Seat"], designations=["Seat 10"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
        Person(name="Dave", roles=["Seat"], designations=["Seat 1"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
        Person(name="Eve", roles=["Council"], designations=["Ward 1"], updated_at="2024-01-01", jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc", source_urls=[]),
    ]
    sorted_people = sort_people(people)
    assert [p.name for p in sorted_people] == ["Bob", "Eve", "Alice", "Dave", "Carol"]

def test_sort_roles_no_priority(monkeypatch):
    monkeypatch.setattr("utils.people_utils.get_role_priority", lambda *_: {})
    monkeypatch.setattr("utils.people_utils.get_designation_priority", lambda: {})
    roles = ["Seat 2", "Seat 1", "Seat 10"]
    assert sort_roles(roles) == ["Seat 1", "Seat 2", "Seat 10"]
