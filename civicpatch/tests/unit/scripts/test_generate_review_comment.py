import pytest
from datetime import datetime, timezone
from typing import List

from scripts.generate_review_comment import generate_review_comment
from schemas import (
    Person, PipelineContext, PipelineStatus,
    MergeRecordsAcrossLLMsStep, FieldComparison
)
from tests.factories.pipeline_context import pipeline_context_factory

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
    context = pipeline_context_factory({
        PipelineStatus.MERGE_RECORDS_ACROSS_LLMS: MergeRecordsAcrossLLMsStep(
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
    
    # Verify that empty strings don't appear in the table for LLM values
    # Check that there isn't a pattern like "| | |" which would indicate empty cells
    lines = comment.split("\n")
    for line in lines:
        if line.strip().startswith("| email"):
            # This is the data row for the email field
            # It should contain "(missing)" and not have empty cells
            parts = [p.strip() for p in line.split("|")]
            # parts should be: ['', 'email', '0.50', 'john@city.gov', '(missing)', 'john@city.gov', '']
            # or: ['', 'email', '0.50', 'john@city.gov', '**john@city.gov**', 'john@city.gov', '']
            # The openai column should not be empty
            assert len(parts) > 4, f"Expected at least 5 columns in line: {line}"
            openai_column = parts[4]  # The openai column (0-indexed: '', field, score, gemini, openai, final)
            assert openai_column != "", f"Expected openai column to not be empty, got: {parts}"
            assert "(missing)" in openai_column or "john@city.gov" in openai_column, \
                f"Expected openai column to contain '(missing)' or a value, got: {openai_column}"


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
    
    context = pipeline_context_factory({
        PipelineStatus.MERGE_RECORDS_ACROSS_LLMS: MergeRecordsAcrossLLMsStep(
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
