import pytest
from datetime import datetime, timezone
from typing import Dict, List, Any

from domain.models import Person
from jobs.people_collector.steps.step_07_merge_records_across_llms.merge_records_across_llms import (
    merge_records_across_llms,
    group_records_across_llms,
    merge_group_across_llms
)
from jobs.people_collector.schemas import (
    WorkflowStatus,
    ProcessPageContentStep,
    MergeRecordsAcrossLLMsStep, 
    MergeRecordsWithinLLMStep, 
    ResearchMunicipalityStep
)
from tests.factories.workflow_context import workflow_context_factory

pytestmark = pytest.mark.unit


def create_person(name: str, roles: List[str], emails: List[str] = [], source_urls: List[str] = []) -> Person:
    """Helper to create a Person with minimal required fields"""
    if source_urls is None:
        source_urls = ["test_source"]
    
    return Person(
        name=name,
        other_names=[],
        roles=roles,
        divisions=["City"] if roles else [],

        emails=emails,
        phones=[],
        urls=[],

        start_date="",
        end_date="",
        image="",
        cdn_image="",
        source_urls=source_urls,
        jurisdiction_ocdid="test_city",
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )


def test_merge_records_across_llms():
    """Test that all expected people are present in the merged results"""
    
    # Create test data with people across different LLMs
    people_by_llm = {
        "gpt4": [
            create_person("John Smith", ["Mayor"], ["john@city.gov"], ["city_website"]),
            create_person("Jane Doe", ["Council Member"], ["jane@city.gov"], ["city_website"]),
        ],
        "claude": [
            create_person("John Smith", ["Mayor"], ["john@city.gov"], ["news_article"]),  # Same person
            create_person("Jane Doe", ["Mayor"], ["jane@city.gov"], ["city_website"]),
        ],
        "gemini": [
            create_person("John Smith", ["Mayor"], ["john.smith@city.gov"], ["government_db"]),  # Same person, different email
            create_person("Alice Green", ["Treasurer"], ["alice@city.gov"], ["government_db"]),  # Only in gemini - should be removed
        ]
    }
    
    # Create pipeline context using factory with correct enum keys
    context = workflow_context_factory({
        WorkflowStatus.MERGE_RECORDS_WITHIN_LLM: MergeRecordsWithinLLMStep(
            people_by_llm=people_by_llm,
        ),
        WorkflowStatus.RESEARCH_MUNICIPALITY: ResearchMunicipalityStep(
            government_type="city",
            people=[],
            elected_officials=[],
        ),
        WorkflowStatus.PROCESS_PAGE_CONTENT: ProcessPageContentStep(
            raw_records_by_llm={},
            records_by_llm={}
        ),
    })
    
    # Test the function
    result = merge_records_across_llms(context)
    
    # Basic structure assertions
    assert isinstance(result, MergeRecordsAcrossLLMsStep)
    assert isinstance(result.people, list)
    assert len(result.people) > 0
    
    # Get all names in results
    result_names = {person.name for person in result.people}
    # Only people who appear in multiple LLMs should remain
    expected_names = {"John Smith", "Jane Doe"}  
    
    # All expected people should be present
    assert result_names == expected_names, f"Expected {expected_names}, got {result_names}"
    
    john = next(p for p in result.people if p.name == "John Smith")
    assert "Mayor" in john.roles


def test_exact_name_match():
    people_by_llm = {
        "llm1": [create_person("Alice", ["A"])],
        "llm2": [create_person("Alice", ["B"])]
    }
    groups = group_records_across_llms({}, people_by_llm)
    assert len(groups) == 1
    assert set(groups[0].keys()) == {"llm1", "llm2"}
    assert all(p.name == "Alice" for ps in groups[0].values() for p in ps)

def test_weak_tie_grouping():
    people_by_llm = {
        "llm1": [create_person("Gem Smitch", ["A"])],
        "llm2": [create_person("Gem Smitch", ["A"])],
        "llm3": [create_person("Idaho Evans", ["B"])]
    }
    groups = group_records_across_llms({}, people_by_llm)
    # Should group llm1 and llm2 together, llm3 separate
    assert len(groups) == 2

def test_mixed_name_and_weak_tie():
    people_by_llm = {
        "llm1": [create_person("Bob Idaho", ["A"]), create_person("Alex H. Smitch", ["C"])],
        "llm2": [create_person("Bob Idaho", ["B"]), create_person("Alex B. Smitch", ["C"])]
    }
    # Alex H. Smitch and Alex B. Smitch should be grouped by weak tie, Bob by exact match
    groups = group_records_across_llms({}, people_by_llm)
    print("groups found:", groups)
    names = [set(p.name for ps in g.values() for p in ps) for g in groups]
    assert len(groups) == 2
    assert {"Bob Idaho"} in names
    assert {"Alex H. Smitch", "Alex B. Smitch"} in names

def test_no_people():
    people_by_llm = {"llm1": [], "llm2": []}
    groups = group_records_across_llms({}, people_by_llm)
    assert groups == []

def test_merge_group_across_llms_combines_other_names():
    """Test that merge_group_across_llms combines other_names correctly."""
    group = [
        Person(name="John Doe", other_names=["J. Doe", "Johnny"], roles=["Mayor"], divisions=[], emails=[], phones=[], urls=[], start_date=None, end_date=None, image=None, cdn_image=None, jurisdiction_ocdid="ocd-division/country:us/state:ca/place:someplace", source_urls=["test"], updated_at=""),
        Person(name="Johnny", other_names=["Johnathan Doe"], roles=["Council"], divisions=[], emails=[], phones=[], urls=[], start_date=None, end_date=None, image=None, cdn_image=None, jurisdiction_ocdid="ocd-division/country:us/state:ca/place:someplace", source_urls=["test"], updated_at="")
    ]
    jurisdiction_ocdid = "ocd-division/country:us/state:ca/place:someplace"

    merged_person = merge_group_across_llms(group, jurisdiction_ocdid)

    assert merged_person.name == "John Doe"
    assert set(merged_person.other_names) == {"J. Doe", "Johnny", "Johnathan Doe"}