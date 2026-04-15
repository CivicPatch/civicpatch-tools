import pytest
from domain.models import Official

from shared.utils.review_utils import get_identity_issues
from runners.people_collector.schemas import (
    PipelineStatus,
    MergeRecordsAcrossLLMsStep,
    FormatOutputStep,
    ResearchMunicipalityStep,
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

DRASS_IDENTITIES = {"michelle drass": ["michelle d rass"]}

def test_direct_name_match():
    officials = [make_official("michelle drass")]
    people = [make_official("michelle drass")]
    errors = get_identity_issues(research_people=officials, people=people, identities=DRASS_IDENTITIES)
    assert errors == []

def test_alias_match():
    people = [make_official("michelle d rass")]
    officials = [make_official("michelle drass")]
    errors = get_identity_issues(research_people=officials, people=people, identities=DRASS_IDENTITIES)
    assert errors == []

def test_missing_official():
    people = [make_official("john smith")]
    officials = [make_official("michelle drass")]
    errors = get_identity_issues(research_people=officials, people=people, identities=DRASS_IDENTITIES)
    assert errors == [
        "Extra official: john smith",
        "Missing official: michelle drass"
    ]

def test_multiple_officials_some_missing():
    people = [make_official("michelle d rass"), make_official("john smith")]
    officials = [make_official("michelle drass"), make_official("jane smith")]
    errors = get_identity_issues(research_people=officials, people=people, identities=DRASS_IDENTITIES)
    assert errors == [
        "Extra official: john smith",
        "Missing official: jane smith"
    ]

def test_extra_official_in_people():
    people = [make_official("michelle drass"), make_official("john smith")]
    officials = [make_official("michelle drass")]
    errors = get_identity_issues(research_people=officials, people=people, identities=DRASS_IDENTITIES)
    assert errors == ["Extra official: john smith"]

def test_extra_official_in_research():
    people = [make_official("michelle d rass")]
    officials = [make_official("michelle drass"), make_official("jane smith")]
    errors = get_identity_issues(research_people=officials, people=people, identities=DRASS_IDENTITIES)
    assert errors == ["Missing official: jane smith"]

def test_both_extra_and_missing_officials():
    people = [make_official("michelle d rass"), make_official("john smith")]
    officials = [make_official("michelle drass"), make_official("jane smith")]
    errors = get_identity_issues(research_people=officials, people=people, identities=DRASS_IDENTITIES)
    assert errors == [
        "Extra official: john smith",
        "Missing official: jane smith"
    ]

def test_no_officials():
    errors = get_identity_issues(research_people=[], people=[], identities={})
    assert errors == []
