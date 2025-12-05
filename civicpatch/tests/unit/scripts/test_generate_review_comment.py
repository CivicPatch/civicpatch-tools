import pytest
from datetime import datetime, timezone
from typing import List

from scripts.generate_review_comment import generate_review_comment
from domain.models import Person
from jobs.people_collector.schemas import (
    WorkflowStatus,
    MergeRecordsAcrossLLMsStep, 
    FieldComparison
)
from tests.factories.workflow_context import workflow_context_factory

pytestmark = pytest.mark.unit

def create_person(name: str, roles: List[str], email: str = "") -> Person:
    """Helper to create a Person with minimal required fields"""
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
        sources=["test_source"],
        jurisdiction_id="test_city",
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )


def test_generate_review_comment_with_missing_llm_values():
    """Test that disagreements show '(missing)' for LLMs that don't have values, not empty strings"""
    
    # Create a person that exists in both LLMs for the merged result
    john = create_person("John Smith", ["Mayor"], "john@city.gov")
    
    # Create disagreements where one LLM is missing from llm_values
    # This simulates the case where a person exists in some LLMs but not others
    disagreements = {
        "John Smith": [
            FieldComparison(
                field="email",
                merged_value="john@city.gov",
                # Only google_gemini has a value, openai is missing from this dict
                llm_values={"google_gemini": "john@city.gov"},
                disagreement_score=0.5
            )
        ]
    }
    
    # Create pipeline context with disagreements
    context = workflow_context_factory({
        WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS: MergeRecordsAcrossLLMsStep(
            people=[john],
            agreement_score=85.0,
            disagreements=disagreements,
            missing_people=[],
            validation_errors=[]
        )
    })
    
    # Generate the comment
    comment = generate_review_comment(context, [john])
    
    # The comment should contain the disagreements section
    assert "### Disagreements" in comment
    
    # The comment should show "(missing)" for the openai column, not an empty string
    # The table should look like:
    # | Field | Disagreement Score | gemini | openai | final_value |
    # | email | 0.50 | john@city.gov | (missing) | john@city.gov |
    assert "(missing)" in comment, "Expected '(missing)' to appear in the comment for LLMs without values"
    
    # Verify that the openai column shows "(missing)" and not an empty string
    lines = comment.split("\n")
    for line in lines:
        if line.strip().startswith("| email"):
            # This is the data row for the email field
            # Parse the columns
            parts = [p.strip() for p in line.split("|")]
            # Expected format: ['', 'field', 'score', 'gemini', 'openai', 'final', '']
            assert len(parts) >= 6, f"Expected at least 6 columns in line: {line}"
            
            # Column indices: 0='', 1=field, 2=score, 3=gemini, 4=openai, 5=final, 6=''
            OPENAI_COLUMN_INDEX = 4
            openai_column = parts[OPENAI_COLUMN_INDEX]
            
            assert openai_column != "", f"Expected openai column to not be empty, got: {parts}"
            assert "(missing)" in openai_column, \
                f"Expected openai column to contain '(missing)', got: {openai_column}"


def test_generate_review_comment_with_all_llms_present():
    """Test that disagreements are displayed correctly when all LLMs have values"""
    
    jane = create_person("Jane Doe", ["Council Member"], "jane@city.gov")
    
    disagreements = {
        "Jane Doe": [
            FieldComparison(
                field="email",
                merged_value="jane@city.gov",
                llm_values={
                    "google_gemini": "jane@city.gov",
                    "openai": "jane.doe@city.gov"  # Different value
                },
                disagreement_score=0.3
            )
        ]
    }
    
    context = workflow_context_factory({
        WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS: MergeRecordsAcrossLLMsStep(
            people=[jane],
            agreement_score=90.0,
            disagreements=disagreements,
            missing_people=[],
            validation_errors=[]
        )
    })
    
    comment = generate_review_comment(context, [jane])
    
    assert "### Disagreements" in comment
    assert "jane@city.gov" in comment
    assert "jane.doe@city.gov" in comment
    
    # Both values should appear, not "(missing)"
    lines = comment.split("\n")
    for line in lines:
        if line.strip().startswith("| email"):
            assert "jane@city.gov" in line
            assert "jane.doe@city.gov" in line or "**jane.doe@city.gov**" in line
