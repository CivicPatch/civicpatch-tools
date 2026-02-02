import pytest
from datetime import datetime, timezone
from typing import List
from domain.models import Official

from scripts.generate_review_comment import (generate_review_comment, get_identity_mismatches)
from domain.models import Person
from jobs.people_collector.schemas import (
    WorkflowStatus,
    MergeRecordsAcrossLLMsStep, 
    FormatOutputStep,
    WorkflowConfig,
    FieldComparison,
    ResearchMunicipalityStep,
    ResearchedPerson,
)
from utils.people_utils import person_to_official
import shared.utils.config_utils as config_utils
from tests.factories.workflow_context import workflow_context_factory

pytestmark = pytest.mark.unit

designation_configs = config_utils.get_designations()

def create_person(name: str, roles: List[str], email: str = "") -> Person:
    """Helper to create a Person with minimal required fields"""
    return Person(
        name=name,
        roles=roles,
        divisions=["City"] if roles else [],
        emails=[email],
        phones=[],
        urls=[],
        start_date="",
        end_date="",
        image="",
        cdn_image="",
        source_urls=["test_source"],
        jurisdiction_ocdid="test_city",
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )


def test_generate_review_comment_with_missing_llm_values():
    """Test that disagreements show '(missing)' for LLMs that don't have values, not empty strings"""
    
    # Create a person that exists in both LLMs for the merged result
    john = create_person("John Smith", ["Mayor"], "john@city.gov")
    john_official = person_to_official(designation_configs, john)
    
    # Create disagreements where one LLM is missing from llm_values
    disagreements = {
        "John Smith": [
            FieldComparison(
                field="email",
                merged_value="john@city.gov",
                llm_values={"google_gemini": "john@city.gov"},
                disagreement_score=0.5
            )
        ]
    }
    
    # Create pipeline context with disagreements
    context = workflow_context_factory({
        WorkflowStatus.RESEARCH_MUNICIPALITY: ResearchMunicipalityStep(
            people=[],
            elected_officials=[]
        ),
        WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS: MergeRecordsAcrossLLMsStep(
            people=[john],
            agreement_score=85.0,
            disagreements=disagreements,
            missing_people=[],
            validation_errors=[]
        ),
        WorkflowStatus.FORMAT_OUTPUT: FormatOutputStep(
            officials=[john_official],
            config=WorkflowConfig(
                url="https://city.gov",
                name="City",
            )
        )
    })
    
    # Generate the comment
    review_decision = generate_review_comment(context, [john_official])
    comment = review_decision.comment
    
    # The comment should contain the disagreements section
    assert "### Disagreements" in comment
    
    # The comment should show "(missing)" for the openai column, not an empty string
    assert "(missing)" in comment, "Expected '(missing)' to appear in the comment for LLMs without values"
    
    # Verify that the openai column shows "(missing)" and not an empty string
    lines = comment.split("\n")
    for line in lines:
        if line.strip().startswith("| email"):
            parts = [p.strip() for p in line.split("|")]
            assert len(parts) >= 6, f"Expected at least 6 columns in line: {line}"
            OPENAI_COLUMN_INDEX = 4
            openai_column = parts[OPENAI_COLUMN_INDEX]
            assert openai_column != "", f"Expected openai column to not be empty, got: {parts}"
            assert "(missing)" in openai_column, \
                f"Expected openai column to contain '(missing)', got: {openai_column}"


def test_generate_review_comment_with_all_llms_present():
    """Test that disagreements are displayed correctly when all LLMs have values"""
    
    jane = create_person("Jane Doe", ["Council Member"], "jane@city.gov")
    jane_official = person_to_official(designation_configs, jane)
    
    disagreements = {
        "Jane Doe": [
            FieldComparison(
                field="email",
                merged_value="jane@city.gov",
                llm_values={
                    "google_gemini": "jane@city.gov",
                    "openai": "jane.doe@city.gov"
                },
                disagreement_score=0.3
            )
        ]
    }
    
    context = workflow_context_factory({
        WorkflowStatus.RESEARCH_MUNICIPALITY: ResearchMunicipalityStep(
            people=[],
            elected_officials=[]
        ),
        WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS: MergeRecordsAcrossLLMsStep(
            people=[jane],
            agreement_score=90.0,
            disagreements=disagreements,
            missing_people=[],
            validation_errors=[]
        ),
        WorkflowStatus.FORMAT_OUTPUT: FormatOutputStep(
            officials=[jane_official],
            config=WorkflowConfig(
                url="https://city.gov",
                name="City",
            )
        )
    })
    
    review_decision = generate_review_comment(context, [jane_official])
    comment = review_decision.comment
    
    assert "### Disagreements" in comment
    assert "jane@city.gov" in comment
    assert "jane.doe@city.gov" in comment
    
    # Both values should appear, not "(missing)"
    lines = comment.split("\n")
    for line in lines:
        if line.strip().startswith("| email"):
            assert "jane@city.gov" in line
            assert "jane.doe@city.gov" in line or "**jane.doe@city.gov**" in line

def make_official(name):
    return Official(
        name=name,
        roles=["mayor"],
        divisions=[],
        emails=[],
        phones=[],
        urls=[],
        start_date="",
        end_date="",
        image="",
        cdn_image="",
        source_urls=[],
        jurisdiction_ocdid="",
        updated_at="",
    )

def test_direct_name_match():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    research = ResearchMunicipalityStep(
        people=[],
        elected_officials=[ResearchedPerson(name="michelle drass", roles=["mayor"], designations=[])]
    )
    people = [make_official("michelle drass")]
    errors = get_identity_mismatches(research, config, people)
    assert errors == []

def test_alias_match():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    research = ResearchMunicipalityStep(
        people=[],
        elected_officials=[ResearchedPerson(name="michelle drass", roles=["mayor"], designations=[])]
    )
    people = [make_official("michelle d rass")]
    errors = get_identity_mismatches(research, config, people)
    assert errors == []

def test_missing_official():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    research = ResearchMunicipalityStep(
        people=[],
        elected_officials=[ResearchedPerson(name="michelle drass", roles=["mayor"], designations=[])]
    )
    people = [make_official("john smith")]
    errors = get_identity_mismatches(research, config, people)
    assert errors == [
        "Extra official: john smith",
        "Missing official: michelle drass"
    ]

def test_multiple_officials_some_missing():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    research = ResearchMunicipalityStep(
        people=[],
        elected_officials=[
            ResearchedPerson(name="michelle drass", roles=["mayor"], designations=[]),
            ResearchedPerson(name="jane smith", roles=["council"], designations=[])
        ]
    )
    people = [make_official("michelle d rass"), make_official("john smith")]
    errors = get_identity_mismatches(research, config, people)
    assert errors == [
        "Extra official: john smith",
        "Missing official: jane smith"
    ]

def test_extra_official_in_people():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    research = ResearchMunicipalityStep(
        people=[],
        elected_officials=[ResearchedPerson(name="michelle drass", roles=["mayor"], designations=[])]
    )
    people = [make_official("michelle drass"), make_official("john smith")]
    errors = get_identity_mismatches(research, config, people)
    assert errors == ["Extra official: john smith"]

def test_extra_official_in_research():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    research = ResearchMunicipalityStep(
        people=[],
        elected_officials=[
            ResearchedPerson(name="michelle drass", roles=["mayor"], designations=[]),
            ResearchedPerson(name="jane smith", roles=["council"], designations=[])
        ]
    )
    people = [make_official("michelle d rass")]
    errors = get_identity_mismatches(research, config, people)
    assert errors == ["Missing official: jane smith"]

def test_both_extra_and_missing_officials():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    research = ResearchMunicipalityStep(
        people=[],
        elected_officials=[
            ResearchedPerson(name="michelle drass", roles=["mayor"], designations=[]),
            ResearchedPerson(name="jane smith", roles=["council"], designations=[])
        ]
    )
    people = [make_official("michelle d rass"), make_official("john smith")]
    errors = get_identity_mismatches(research, config, people)
    assert errors == [
        "Extra official: john smith",
        "Missing official: jane smith"
    ]

def test_no_officials():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={}
    )
    research = ResearchMunicipalityStep(
        people=[],
        elected_officials=[]
    )
    people = []
    errors = get_identity_mismatches(research, config, people)
    assert errors == []
