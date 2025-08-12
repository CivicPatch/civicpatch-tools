import utils.config_utils as config_utils
from steps.step_06_merge_records_within_source.merge_records_within_source import (
    merge_field, merge_roles, normalize_division, merge_divisions, records_to_llm_person
)
import pytest
from schemas import LLMPerson, LLMDataPoint, ProcessedLLMPeople

def make_llm_person(name, roles=None, divisions=None, phone=None, email=None, website=None):
    dp = lambda val: LLMDataPoint(data=val, llm_confidence=1.0, llm_confidence_reason="test")
    return LLMPerson(
        name=name,
        roles=[dp(r) for r in (roles or [])],
        divisions=[dp(d) for d in (divisions or [])],
        phone_number=dp(phone) if phone else dp(None),
        email=dp(email) if email else dp(None),
        website=dp(website) if website else dp(None),
        start_date=dp(None),
        end_date=dp(None)
    )

def get_real_role_alias_map():
    # Use your real config utility to get the alias map for a government type
    government_types = config_utils.get_government_types()
    # Pick a type for your test, e.g. "mayor_council"
    role_configs = government_types["mayor_council"]["roles"]
    alias_map = {}
    for entry in role_configs:
        canonical = entry["role"]
        alias_map[canonical.lower()] = canonical
        for alias in entry.get("aliases", []):
            alias_map[alias.lower()] = canonical
    return alias_map

def test_division_alias_map_real_config():
    # Load the real divisions.yaml
    alias_map = config_utils.get_division_alias_map()

    # Test a few real-world cases
    assert normalize_division("citywide", alias_map) == "at-large"
    assert normalize_division("ward 5", alias_map) == "ward 5"
    assert normalize_division("council ward 2", alias_map) == "ward 2"
    assert normalize_division("district east", alias_map) == "district east"
    assert normalize_division("at large", alias_map) == "at-large"
    assert normalize_division("city wide", alias_map) == "at-large"
    assert normalize_division("unknown", alias_map) == "unknown"

def test_merge_field_empty():
    # No values present
    p1 = make_llm_person("Alice")
    assert merge_field([p1], "phone_number") is None

def test_merge_field_confidence_tiebreak():
    # Two values, same data, different confidence
    dp = lambda val, conf: LLMDataPoint(data=val, llm_confidence=conf, llm_confidence_reason="test")
    p1 = make_llm_person("Alice")
    p1.phone_number = dp("555-1234", 0.8)
    p2 = make_llm_person("Alice")
    p2.phone_number = dp("555-1234", 0.9)
    result = merge_field([p1, p2], "phone_number")
    assert result.data == "555-1234"
    assert result.llm_confidence == 0.9

def test_merge_roles_empty():
    # No roles present
    p1 = make_llm_person("Bob")
    assert merge_roles([p1], {}) == []

def test_merge_roles_multiple_roles():
    role_alias_map = get_real_role_alias_map()
    p1 = make_llm_person("Bob", roles=["Council Member"])
    p2 = make_llm_person("Bob", roles=["Council Member"])
    p3 = make_llm_person("Bob", roles=["Mayor"])
    assert merge_roles([p1, p2, p3], role_alias_map) == ["council member", "mayor"]

def test_merge_roles_deduplication():
    role_alias_map = get_real_role_alias_map()
    p1 = make_llm_person("Sam", roles=["Council Member", "Mayor"])
    p2 = make_llm_person("Sam", roles=["Council Member"])
    p3 = make_llm_person("Sam", roles=["Mayor"])
    assert merge_roles([p1, p2, p3], role_alias_map) == ["council member", "mayor"]

def test_normalize_division_suffix():
    alias_map = config_utils.get_division_alias_map()
    # Suffix is preserved and cleaned
    assert normalize_division("ward 5!", alias_map) == "ward 5"
    assert normalize_division("council ward east", alias_map) == "ward east"

def test_merge_divisions_empty():
    alias_map = config_utils.get_division_alias_map()
    p1 = make_llm_person("Carol")
    assert merge_divisions(alias_map, [p1]) == []

def test_merge_divisions_tiebreak():
    alias_map = config_utils.get_division_alias_map()
    p1 = make_llm_person("Dana", divisions=["ward 1"])
    p2 = make_llm_person("Dana", divisions=["ward 1"])
    p3 = make_llm_person("Dana", divisions=["ward 2"])
    assert merge_divisions(alias_map, [p1, p2, p3]) == ["ward 1", "ward 2"]

def test_merge_divisions_unique_all():
    alias_map = config_utils.get_division_alias_map()
    p1 = make_llm_person("Dana", divisions=["ward 1"])
    p2 = make_llm_person("Dana", divisions=["ward 1"])
    p3 = make_llm_person("Dana", divisions=["ward 2"])
    p4 = make_llm_person("Dana", divisions=["council ward 3"])
    result = merge_divisions(alias_map, [p1, p2, p3, p4])
    assert result == ["ward 1", "ward 2", "ward 3"]

def test_merge_divisions_deduplication():
    alias_map = config_utils.get_division_alias_map()
    p1 = make_llm_person("Dana", divisions=["ward 1", "ward 2"])
    p2 = make_llm_person("Dana", divisions=["ward 2", "ward 3"])
    p3 = make_llm_person("Dana", divisions=["ward 1"])
    result = merge_divisions(alias_map, [p1, p2, p3])
    assert result == ["ward 1", "ward 2", "ward 3"]

def test_records_to_llm_person_all_fields():
    role_alias_map = get_real_role_alias_map()
    division_alias_map = config_utils.get_division_alias_map()
    p1 = make_llm_person("Eve", roles=["Council Member"], divisions=["ward 5"], phone="555-1234", email="eve@city.org", website="city.org/eve")
    p2 = make_llm_person("Eve", roles=["Council Member"], divisions=["council ward 5"], phone="555-1234", email="eve@city.org", website="city.org/eve")
    processed = ProcessedLLMPeople(names=["Eve"], records=[p1, p2])
    merged = records_to_llm_person(
        name="Eve",
        role_alias_map=role_alias_map,
        division_alias_map=division_alias_map,
        processed_llm_people=processed
    )
    assert merged.name == "Eve"
    assert merged.roles == ["council member"]
    assert merged.divisions == ["ward 5"]
    assert merged.phone_number == "555-1234"
    assert merged.email == "eve@city.org"
    assert merged.website == "city.org/eve"