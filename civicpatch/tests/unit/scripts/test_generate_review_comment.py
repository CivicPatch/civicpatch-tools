import pytest
from domain.models import Official

from shared.utils.review_utils import get_identity_issues
from jobs.people_collector.schemas import (
    WorkflowStatus,
    MergeRecordsAcrossLLMsStep,
    FormatOutputStep,
    WorkflowConfig,
    ResearchMunicipalityStep,
    ResearchedPerson,
)

pytestmark = pytest.mark.unit


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
        id=""
    )

def test_direct_name_match():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )

    officials = [make_official("michelle drass")]
    people = [make_official("michelle drass")]
    errors = get_identity_issues(research_people=officials, people=people, identities=config.identities or {})
    assert errors == []

def test_alias_match():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    people = [make_official("michelle d rass")]
    officials = [make_official("michelle drass")]
    errors = get_identity_issues(research_people=officials, people=people, identities=config.identities or {})
    assert errors == []

def test_missing_official():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    people = [make_official("john smith")]
    officials = [make_official("michelle drass")]
    errors = get_identity_issues(research_people=officials, people=people, identities=config.identities or {})
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
    officials = [make_official("michelle drass"), make_official("jane smith")]
    errors = get_identity_issues(research_people=officials, people=people, identities=config.identities or {})
    assert errors == [
        "Extra official: john smith",
        "Missing official: jane smith"
    ]

def test_extra_official_in_people():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    people = [make_official("michelle drass"), make_official("john smith")]

    officials = [make_official("michelle drass")]
    errors = get_identity_issues(research_people=officials, people=people, identities=config.identities or {})
    assert errors == ["Extra official: john smith"]

def test_extra_official_in_research():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    
    people = [make_official("michelle d rass")]
    officials = [make_official("michelle drass"), make_official("jane smith")]
    errors = get_identity_issues(research_people=officials, people=people, identities=config.identities or {})
    assert errors == ["Missing official: jane smith"]

def test_both_extra_and_missing_officials():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={"michelle drass": ["michelle d rass"]}
    )
    
    people = [make_official("michelle d rass"), make_official("john smith")]
    officials = [make_official("michelle drass"), make_official("jane smith")]
    errors = get_identity_issues(research_people=officials, people=people, identities=config.identities or {})
    assert errors == [
        "Extra official: john smith",
        "Missing official: jane smith"
    ]

def test_no_officials():
    config = WorkflowConfig(
        url="https://city.gov",
        identities={}
    )
    
    people = []
    errors = get_identity_issues(research_people=[], people=people, identities=config.identities or {})
    assert errors == []
