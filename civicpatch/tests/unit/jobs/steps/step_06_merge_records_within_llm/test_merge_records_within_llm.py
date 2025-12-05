import pytest
from domain.models import Person
from jobs.people_collector.schemas import (
    LLMPerson, WorkflowStatus 
)
from jobs.people_collector.steps.step_06_merge_records_within_llm.merge_records_within_llm import (
    merge_field, merge_roles, merge_divisions, merge_llm_people_to_person, merge_records_within_llm
)
from shared.utils.config_utils import get_role_alias_map, get_division_alias_map

def make_llm_person(name, roles=None, divisions=None, phone=None, email=None, website=None):
    """Helper function to create LLMPerson objects for testing"""
    return LLMPerson(
        name=name,
        roles=[{"data": r} for r in (roles or [])],
        divisions=[{"data": d} for d in (divisions or [])],
        phone_number={"data": phone} if phone else None,
        email={"data": email} if email else None,
        website={"data": website} if website else None,
        start_date=None,
        end_date=None
    )

def test_merge_field():
    """Test merging single value fields"""
    p1 = make_llm_person("Alice")
    p1.phone_number = {"data": "555-1234"}
    p2 = make_llm_person("Alice")
    p2.phone_number = {"data": "555-1234"}
    result = merge_field([p1, p2], "phone_number")
    assert result == "555-1234"

def test_merge_roles():
    """Test merging roles across records with normalization"""
    p1 = make_llm_person("Sam", roles=["Council Member", "Mayor"])
    p2 = make_llm_person("Sam", roles=["Council Member", "Treasurer"])
    government_type = "mayor_council"
    result = merge_roles([p1, p2], government_type)
    role_alias_map = get_role_alias_map(government_type)
    normalized_roles = {role_alias_map.get(role.lower(), role) for role in ["Council Member", "Mayor", "Treasurer"]}
    assert set(result) == normalized_roles  # All unique normalized roles

def test_merge_divisions():
    """Test merging divisions across records with normalization"""
    p1 = make_llm_person("Dana", divisions=["Ward 1", "Ward 2"])
    p2 = make_llm_person("Dana", divisions=["Ward 2", "Ward 3"])
    division_alias_map = get_division_alias_map()
    result = merge_divisions([p1, p2])
    normalized_divisions = set()
    for division in ["Ward 1", "Ward 2", "Ward 3"]:
        for alias, canonical in division_alias_map.items():
            if division.lower().startswith(alias):
                suffix = division[len(alias):].strip()
                normalized_divisions.add(f"{canonical} {suffix}" if suffix else canonical)
                break
        else:
            normalized_divisions.add(division)
    assert set(result) == normalized_divisions  # All unique normalized divisions

def test_merge_llm_people_to_person():
    """Test merging multiple LLMPerson records into a single Person with normalized roles and divisions"""
    p1 = make_llm_person(
        name="Eve",
        roles=["Council Member", "Treasurer"],
        divisions=["Ward 5", "Ward 6"],
        phone="555-1234",
        email="eve@city.org"
    )
    p2 = make_llm_person(
        name="Eve",
        roles=["Council Member", "Mayor"],
        divisions=["Ward 5", "Ward 7"],
        phone="555-1234",
        email="eve@city.org"
    )
    government_type = "mayor_council"
    result = merge_llm_people_to_person("Eve", [p1, p2], government_type)
    
    # Convert to dict for comparison since we expect dictionary output
    result_dict = result.model_dump()
    role_alias_map = get_role_alias_map(government_type)
    division_alias_map = get_division_alias_map()
    normalized_roles = {role_alias_map.get(role.lower(), role) for role in ["Council Member", "Treasurer", "Mayor"]}
    normalized_divisions = set()
    for division in ["Ward 5", "Ward 6", "Ward 7"]:
        for alias, canonical in division_alias_map.items():
            if division.lower().startswith(alias):
                suffix = division[len(alias):].strip()
                normalized_divisions.add(f"{canonical} {suffix}" if suffix else canonical)
                break
        else:
            normalized_divisions.add(division)
    assert result_dict["name"] == "Eve"
    assert set(result_dict["roles"]) == normalized_roles  # All unique normalized roles
    assert set(result_dict["divisions"]) == normalized_divisions  # All unique normalized divisions
    assert result_dict["phone_number"] == "555-1234"
    assert result_dict["email"] == "eve@city.org"

def test_merge_records_within_llm():
    """Test the complete merge process within each source with normalized roles and divisions"""
    # Setup test data
    records_by_llm = {
        "google_gemini": {
            "Alice Johnson": [
                make_llm_person("Alice Johnson", roles=["Council Member", "Mayor"], divisions=["Ward 1", "Ward 2"], phone="123"),
                make_llm_person("Alice Johnson", roles=["Council Member", "Treasurer"], divisions=["Ward 2", "Ward 3"], phone="123")
            ]
        }
    }

    # Create pipeline context
    context = {
        "steps": {
            WorkflowStatus.RESEARCH_MUNICIPALITY.value: {
                "government_type": "mayor_council"
            },
            WorkflowStatus.PROCESS_PAGE_CONTENT.value: {
                "records_by_llm": records_by_llm
            }
        },
        "government_type": "mayor_council"
    }

    # Run the merge step
    result = merge_records_within_llm(context)

    # Assert structure
    assert "steps" in result
    merged_step = result["steps"][WorkflowStatus.MERGE_RECORDS_WITHIN_LLM.value]
    assert "people_by_llm" in merged_step

    # Check results
    people_by_llm = merged_step["people_by_llm"]
    assert len(people_by_llm["google_gemini"]) == 1

    # Check merged record
    alice = people_by_llm["google_gemini"][0]
    role_alias_map = get_role_alias_map("mayor_council")
    division_alias_map = get_division_alias_map()
    normalized_roles = {role_alias_map.get(role.lower(), role) for role in ["Council Member", "Mayor", "Treasurer"]}
    normalized_divisions = set()
    for division in ["Ward 1", "Ward 2", "Ward 3"]:
        for alias, canonical in division_alias_map.items():
            if division.lower().startswith(alias):
                suffix = division[len(alias):].strip()
                normalized_divisions.add(f"{canonical} {suffix}" if suffix else canonical)
                break
        else:
            normalized_divisions.add(division)
    assert alice["name"] == "Alice Johnson"
    assert set(alice["roles"]) == normalized_roles  # All unique normalized roles
    assert set(alice["divisions"]) == normalized_divisions  # All unique normalized divisions
    assert alice["phone_number"] == "123"