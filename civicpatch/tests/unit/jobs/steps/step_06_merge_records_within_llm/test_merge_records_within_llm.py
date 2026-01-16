import pytest
from domain.models import Person
from jobs.people_collector.schemas import (
    LLMPerson, WorkflowStatus 
)
from jobs.people_collector.steps.step_06_merge_records_within_llm.merge_records_within_llm import (
    merge_llm_people_to_person, merge_records_within_llm, get_source_urls
)
from shared.utils.config_utils import get_role_alias_map, get_division_alias_map
from datetime import datetime as Datetime

pytestmark = pytest.mark.unit

def make_llm_person(name, roles=None, divisions=None, phone=None, email=None, url=None, source_url=None):
    """Helper function to create LLMPerson objects for testing"""
    return LLMPerson(
        name=name,
        roles=roles or [],
        divisions=divisions or [],
        phone=phone,
        email=email,
        url=url,
        start_date=None,
        end_date=None,
        image=None,
        source_url=source_url or f"http://source-{name.replace(' ', '').lower()}.com"
    )

def test_merge_llm_people_to_person():
    """Test merging multiple LLMPerson records into a single Person with normalized roles and divisions and correct source_urls"""
    p1 = make_llm_person(
        name="Eve",
        roles=["Council Member", "Treasurer"],
        divisions=["Ward 5", "Ward 6"],
        phone="555-1234",
        email="eve@city.org",
        source_url="http://source1.com"
    )
    p2 = make_llm_person(
        name="Eve",
        roles=["Council Member", "Mayor"],
        divisions=["Ward 5", "Ward 7"],
        phone="555-1234",
        email="eve@city.org",
        source_url="http://source2.com"
    )
    jurisdiction_ocdid = "jurisdiction_id"
    result = merge_llm_people_to_person("Eve", [p1, p2], jurisdiction_ocdid)

    # Check merged fields
    assert result.name == "Eve"
    assert set(result.roles) == {"Council Member", "Treasurer", "Mayor"}
    assert set(result.divisions) == {"Ward 5", "Ward 6", "Ward 7"}
    assert set(result.phones) == {"555-1234"}
    assert set(result.emails) == {"eve@city.org"}
    # Check that both source_urls are present
    assert set(result.source_urls) == {"http://source1.com", "http://source2.com"}
    assert result.jurisdiction_ocdid == jurisdiction_ocdid


def test_get_source_urls_filters_by_unique_contribution():
    # Record 1: contributes only "Mayor" role and "Ward 1" division
    r1 = LLMPerson(
        name="Robert Kubert",
        roles=["Mayor"],
        divisions=["Ward 1"],
        phone=None,
        email=None,
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r1"
    )
    # Record 2: contributes "Mayor", "Council Member" roles, "Ward 2", "Ward 3" divisions, phone, email
    r2 = LLMPerson(
        name="Robert Kubert",
        roles=["Mayor", "Council Member"],
        divisions=["Ward 2", "Ward 3"],
        phone="555-0002",
        email="mayor2@bayonne.org",
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r2"
    )
    # Record 3: contributes only "Mayor" role and "Ward 1" division
    r3 = LLMPerson(
        name="Robert Kubert",
        roles=["Mayor"],
        divisions=["Ward 1"],
        phone=None,
        email=None,
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r3"
    )

    person_records = [r1, r2, r3]

    # Merged person includes all unique values from above
    person = Person(
        name="Robert Kubert",
        roles=["Mayor", "Council Member"],
        divisions=["Ward 1", "Ward 2", "Ward 3"],
        phones=["555-0002"],
        emails=["mayor2@bayonne.org"],
        urls=["https://www.bayonnenj.org/officials/bio/mayor-robert-kubert"],
        jurisdiction_ocdid="test_ocdid",
        source_urls=[],
        updated_at=""
    )

    # Only r2 contributed the most unique values for roles, divisions, phone, email
    expected_urls = {"https://www.bayonnenj.org/r1", "https://www.bayonnenj.org/r2"}

    result = get_source_urls(person_records, person)
    # Should only return r2's source_url for all fields with data
    assert set(result) == expected_urls 