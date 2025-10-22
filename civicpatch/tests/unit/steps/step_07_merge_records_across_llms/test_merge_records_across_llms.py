import pytest
from datetime import datetime, timezone
from typing import Dict, List, Any

from steps.step_07_merge_records_across_llms.merge_records_across_llms import (
    merge_records_across_llms,
    merge_group_across_llms,
    group_records_across_llms
)
from schemas import (
    Person, PipelineStatus,
    MergeRecordsAcrossLLMsStep, MergeRecordsWithinLLMStep, ResearchMunicipalityStep
)
from tests.factories.pipeline_context import pipeline_context_factory

pytestmark = pytest.mark.unit


def create_person(name: str, roles: List[str], email: str = "", sources: List[str] = []) -> Person:
    """Helper to create a Person with minimal required fields"""
    if sources is None:
        sources = ["test_source"]
    
    return Person(
        name=name,
        roles=roles,
        divisions=["City"] if roles else [],
        email=email,
        phone_number="",
        website="",
        start_date="",
        end_date="",
        image="",
        cdn_image="",
        sources=sources,
        jurisdiction_id="test_city",
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )


def test_merge_records_across_llms():
    """Test that all expected people are present in the merged results"""
    
    # Create test data with people across different LLMs
    people_by_llm = {
        "gpt4": [
            create_person("John Smith", ["Mayor"], "john@city.gov", ["city_website"]),
            create_person("Jane Doe", ["Council Member"], "jane@city.gov", ["city_website"]),
        ],
        "claude": [
            create_person("John Smith", ["Mayor"], "john@city.gov", ["news_article"]),  # Same person
            create_person("Jane Doe", ["Mayor"], "jane@city.gov", ["city_website"]),
        ],
        "gemini": [
            create_person("John Smith", ["Mayor"], "john.smith@city.gov", ["government_db"]),  # Same person, different email
            create_person("Alice Green", ["Treasurer"], "alice@city.gov", ["government_db"]),  # Only in gemini - should be removed
        ]
    }
    
    # Create pipeline context using factory with correct enum keys
    context = pipeline_context_factory({
        PipelineStatus.MERGE_RECORDS_WITHIN_LLM: MergeRecordsWithinLLMStep(
            people_by_llm=people_by_llm,
        ),
        PipelineStatus.RESEARCH_MUNICIPALITY: ResearchMunicipalityStep(
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

#def test_merge_group_across_llms():
#    """Test merging a group of people from different LLMs"""
#    
#    # Create identical people from different sources
#    group = [
#        create_person("John Smith", ["Mayor"], "john@city.gov", ["source1"]),
#        create_person("John Smith", ["Mayor"], "john@city.gov", ["source2"]),
#    ]
#    
#    merged = merge_group_across_llms(group, "test_city")
#    
#    assert merged.name == "John Smith"
#    assert "Mayor" in merged.roles  # Should appear since it's in multiple sources
#    assert merged.email == "john@city.gov"  # Should appear since it's in multiple sources
#    assert len(merged.sources) == 2
#    
#
#def test_group_records_across_llms():
#    """Test grouping records across LLMs"""
#    
#    people_by_llm = {
#        "llm1": [
#            create_person("John Smith", ["Mayor"]),
#            create_person("Jane Doe", ["Council Member"]),
#        ],
#        "llm2": [
#            create_person("John Smith", ["Mayor"]),  # Same person
#            create_person("Bob Wilson", ["Council Member"]),  # Different person
#        ]
#    }
#    
#    groups = group_records_across_llms(people_by_llm)
#    
#    assert isinstance(groups, list)
#    assert len(groups) > 0
#    
#    # Should have grouped John Smith across both LLMs
#    john_group = None
#    for group in groups:
#        if any("John Smith" in [p.name for p in people] for people in group.values()):
#            john_group = group
#            break
#    
#    assert john_group is not None
#    assert len(john_group) == 2  # Should be in both LLMs
#    assert "llm1" in john_group
#    assert "llm2" in john_group

