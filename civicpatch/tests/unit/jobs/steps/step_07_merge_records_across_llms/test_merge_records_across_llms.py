import pytest
from datetime import datetime, timezone
from typing import Dict, List, Any

from domain.models import Person
from jobs.people_collector.steps.step_07_merge_records_across_llms.merge_records_across_llms import (
    merge_records_across_llms,
    merge_group_across_llms,
    group_records_across_llms
)
from jobs.people_collector.schemas import (
    WorkflowStatus,
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
        jurisdiction_id="test_city",
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
        )
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
    expected_names = {"John Smith", "Jane Doe", "Alice Green"}  
    
    # All expected people should be present
    assert result_names == expected_names, f"Expected {expected_names}, got {result_names}"
    
    john = next(p for p in result.people if p.name == "John Smith")
    assert "Mayor" in john.roles

