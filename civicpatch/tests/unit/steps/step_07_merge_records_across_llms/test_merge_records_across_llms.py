from steps.step_07_merge_records_across_llms.merge_records_across_llms import merge_people_across_llms
import pytest
from schemas import Person, Disagreement, MissingPerson, PipelineStatus, PipelineContext
from steps.step_07_merge_records_across_llms import (
    merge_records_across_llms
)

def test_merge_records_across_llms():
    """Test merging records across different sources"""
    # Setup test data - simulate output from previous step
    people_by_llm = {
        "google_gemini": [
            {
                "name": "Alice Johnson",
                "roles": ["Council Member"],
                "divisions": ["Ward 1"],
                "phone_number": "123",
                "email": "alice@example.com",
                "website": "",
                "start_date": "",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["source a"],
                "updated_at": ""
            }
        ],
        "openai": [
            {
                "name": "Alice Johnson",
                "roles": ["Council Member", "Mayor"],
                "divisions": ["Ward 1"],
                "phone_number": "123",
                "email": "alice@example.com",
                "website": "",
                "start_date": "",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["source a"],
                "updated_at": ""
            }
        ]
    }

    # Create pipeline context
    context = {
        "steps": {
            PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value: {
                "people_by_llm": people_by_llm
            }
        }
    }

    # Run the merge step
    result = merge_records_across_llms(context)

    # Assert structure
    merged_step = result["steps"][PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value]
    assert "people" in merged_step
    assert "agreement_score" in merged_step
    assert "disagreements" in merged_step
    assert "missing_people" in merged_step
    
    # Check merged people
    merged_people = merged_step["people"]
    assert len(merged_people) == 1
    
    merged_person = merged_people[0]
    assert merged_person["name"] == "Alice Johnson"
    assert merged_person["roles"] == ["Council Member"]  # Only role that appears in both sources
    assert merged_person["divisions"] == ["Ward 1"]
    assert merged_person["phone_number"] == "123"
    assert merged_person["email"] == "alice@example.com"
    assert set(merged_person["sources"]) == {"source a"}
    
    # Check agreement score - should be high since most fields match
    assert merged_step["agreement_score"] >= 80.0

    assert len(merged_step["disagreements"]) == 1

    # Check missing people - should be empty since all sources have data
    assert len(merged_step["missing_people"]) == 0


def test_merge_people_across_llms_with_conflicts():
    """Test merging people with conflicting information grouped by source"""
    people_by_llm = {
        "google_gemini": [
            Person.model_validate({
                "name": "Bob Smith",
                "roles": ["Council Member", "Vice Mayor"],
                "divisions": ["District 1", "At Large"],
                "phone_number": "555-0123",
                "email": "bob@city.gov",
                "website": "www.bob.gov",
                "start_date": "2023-01-01",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["source a"],
                "updated_at": ""
            })
        ],
        "openai": [
            Person.model_validate({
                "name": "Bob Smith",
                "roles": ["Council Member"],
                "divisions": ["District 1"],
                "phone_number": "555-0123",
                "email": "bob.smith@city.gov",
                "website": "",
                "start_date": "",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["source b"],
                "updated_at": ""
            })
        ]
    }

    # Test merging
    merged = merge_people_across_llms("Bob Smith", people_by_llm)

    # Assertions
    assert merged.name == "Bob Smith"
    assert merged.roles == ["Council Member"]  # Only role that appears in both sources
    assert merged.divisions == ["District 1"]  # Only division that appears in both sources
    assert merged.phone_number == "555-0123"  # Same in both sources
    assert merged.email == "bob@city.gov"  # Take most common or first
    assert set(merged.sources) == {"source a", "source b"}


def test_merge_people_across_llms_with_correct_sources():
    """Test merging people with correct sources field"""
    people_by_llm = {
        "google_gemini": [
            Person.model_validate({
                "name": "Bob Smith",
                "roles": ["Council Member", "Vice Mayor"],
                "divisions": ["District 1", "At Large"],
                "phone_number": "555-0123",
                "email": "bob@city.gov",
                "website": "www.bob.gov",
                "start_date": "2023-01-01",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["Source A", "Source B"],  # Correct sources from the Person object
                "updated_at": ""
            })
        ],
        "openai": [
            Person.model_validate({
                "name": "Bob Smith",
                "roles": ["Council Member"],
                "divisions": ["District 1"],
                "phone_number": "555-0123",
                "email": "bob.smith@city.gov",
                "website": "",
                "start_date": "",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["Source C"],  # Correct sources from the Person object
                "updated_at": ""
            })
        ]
    }

    # Test merging
    merged = merge_people_across_llms("Bob Smith", people_by_llm)

    # Assertions
    assert merged.name == "Bob Smith"
    assert merged.roles == ["Council Member"]  # Only role that appears in more than one source
    assert merged.divisions == ["District 1"]  # Only division that appears in more than one source
    assert merged.phone_number == "555-0123"  # Same in both sources
    assert merged.email == "bob@city.gov"  # Take most common or first
    assert set(merged.sources) == {"Source A", "Source B", "Source C"}  # Sources should come from the individual Person objects


def test_merge_people_across_llms_with_correct_sources():
    """Test merging people with correct sources field"""
    people_by_llm = {
        "google_gemini": [
            Person.model_validate({
                "name": "Bob Smith",
                "roles": ["Council Member", "Vice Mayor"],
                "divisions": ["District 1", "At Large"],
                "phone_number": "555-0123",
                "email": "bob@city.gov",
                "website": "www.bob.gov",
                "start_date": "2023-01-01",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["Source A", "Source B"],  # Updated field name
                "updated_at": ""
            })
        ],
        "openai": [
            Person.model_validate({
                "name": "Bob Smith",
                "roles": ["Council Member"],
                "divisions": ["District 1"],
                "phone_number": "555-0123",
                "email": "bob.smith@city.gov",
                "website": "",
                "start_date": "",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["Source C"],  # Updated field name
                "updated_at": ""
            })
        ]
    }

    # Test merging
    merged = merge_people_across_llms("Bob Smith", people_by_llm)

    # Assertions
    assert merged.name == "Bob Smith"
    assert merged.roles == ["Council Member"]  # Only role that appears in more than one source
    assert merged.divisions == ["District 1"]  # Only division that appears in more than one source
    assert merged.phone_number == "555-0123"  # Same in both sources
    assert merged.email == "bob@city.gov"  # Take most common or first
    assert set(merged.sources) == {"Source A", "Source B", "Source C"}  # Updated field name


def test_disagreements_and_missing_people():
    """Test disagreements and missing people detection"""
    people_by_llm = {
        "google_gemini": [
            Person.model_validate({
                "name": "Charlie Brown",
                "roles": ["Council Member"],
                "divisions": ["District 1"],
                "phone_number": "555-0123",
                "email": "charlie@city.gov",
                "website": "",
                "start_date": "",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["google_gemini"],
                "updated_at": ""
            })
        ],
        "openai": []
    }

    # Create pipeline context
    context = {
        "steps": {
            PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value: {
                "people_by_llm": people_by_llm
            }
        }
    }

    # Run the merge step
    result = merge_records_across_llms(context)

    # Assert structure
    merged_step = result["steps"][PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value]
    assert "disagreements" in merged_step
    assert "missing_people" in merged_step

    # Check disagreements - should be empty since the person is missing in "openai"
    disagreements = merged_step["disagreements"]
    assert len(disagreements) == 0

    # Check missing people - should detect missing data in "openai"
    missing_people = merged_step["missing_people"]
    assert len(missing_people) == 1
    assert missing_people[0].source == "openai"
    assert missing_people[0].person_name == "Charlie Brown"

    # Check agreement score - should be high since no disagreements were added
    assert merged_step["agreement_score"] == 100.0


def test_disagreements_detection():
    """Test detection of disagreements across sources"""
    people_by_llm = {
        "google_gemini": [
            Person.model_validate({
                "name": "Jane Doe",
                "roles": ["Council Member"],
                "divisions": ["District 1"],
                "phone_number": "555-1234",
                "email": "jane.doe@city.gov",
                "website": "www.janedoe.com",
                "start_date": "2023-01-01",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["source a"],
                "updated_at": ""
            })
        ],
        "openai": [
            Person.model_validate({
                "name": "Jane Doe",
                "roles": ["Council Member", "Mayor"],
                "divisions": ["District 1"],
                "phone_number": "555-5678",
                "email": "jane.doe@city.gov",
                "website": "",
                "start_date": "",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["source b"],
                "updated_at": ""
            })
        ]
    }

    context = {
        "steps": {
            PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value: {
                "people_by_llm": people_by_llm
            }
        }
    }

    # Run the merge step
    result = merge_records_across_llms(context)

    # Assert structure
    merged_step = result["steps"][PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value]
    assert "disagreements" in merged_step

    # Check disagreements
    disagreements = merged_step["disagreements"]
    assert len(disagreements) == 2  # Conflicts in roles and phone_number
    assert any(d.field == "roles" and d.value == "Council Member, Mayor" for d in disagreements)
    assert any(d.field == "phone_number" and d.value == "555-5678" for d in disagreements)


def test_missing_people_detection():
    """Test detection of missing people across sources"""
    people_by_llm = {
        "google_gemini": [
            Person.model_validate({
                "name": "John Smith",
                "roles": ["Council Member"],
                "divisions": ["District 2"],
                "phone_number": "555-9876",
                "email": "john.smith@city.gov",
                "website": "",
                "start_date": "",
                "end_date": "",
                "image": "",
                "cdn_image": "",
                "sources": ["source a"],
                "updated_at": ""
            })
        ],
        "openai": []
    }

    # Create pipeline context
    context = {
        "steps": {
            PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value: {
                "people_by_llm": people_by_llm
            }
        }
    }

    # Run the merge step
    result = merge_records_across_llms(context)

    # Assert structure
    merged_step = result["steps"][PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value]
    assert "missing_people" in merged_step

    # Check missing people
    missing_people = merged_step["missing_people"]
    assert len(missing_people) == 1
    assert missing_people[0].source == "openai"
    assert missing_people[0].person_name == "John Smith"