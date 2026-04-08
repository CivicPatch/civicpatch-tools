import pytest

from jobs.people_collector.schemas import (
    LLMPerson, WorkflowStatus 
)
from jobs.people_collector.steps.step_06_merge_records_within_llm.field_mergers import (
    merge_roles, merge_designations, merge_field
)
from shared.utils.config_utils import get_role_alias_map, get_designation_alias_map

pytestmark = pytest.mark.unit

def make_llm_person(name, roles=None, designations=None, phone=None, email=None, website=None):
    """Helper function to create LLMPerson objects for testing"""
    return LLMPerson(
        name=name,
        other_names=[],
        roles=roles or [],
        designations=designations or [],
        phone={"data": phone} if phone else None,
        email={"data": email} if email else None,
        url={"data": website} if website else None,
        start_date=None,
        end_date=None,
        source_url=""

    )

def test_merge_field():
    """Test merging single value fields"""
    result = merge_field(["555-1234", "555-1234"])
    assert result == "555-1234"

def test_merge_roles():
    """Test merging roles across records with normalization"""
    p1 = make_llm_person("Sam", roles=["Council Member", "Mayor"])
    p2 = make_llm_person("Sam", roles=["Council Member", "Treasurer"])
    result = merge_roles([p1, p2])
    expected_roles = ["Council Member", "Mayor", "Treasurer"]
    assert set(result) == set(expected_roles)  # All unique normalized roles

def test_merge_designations():
    """Test merging designations across records with normalization"""
    p1 = make_llm_person("Dana", designations=["Ward 1", "Ward 2"])
    p2 = make_llm_person("Dana", designations=["Ward 2", "Ward 3"])
    result = merge_designations([p1, p2])
    expected_designations = ["Ward 1", "Ward 2", "Ward 3"]
    assert set(result) == set(expected_designations)  # All unique normalized designations
    