import pytest
from jobs.people_collector.steps.step_08_format_output.format_output import (
    format_output,
    normalize_division,
    maybe_add_fallback_url,
    generate_identities_config,
    find_source_urls,
)
from domain.models import Official
from jobs.people_collector.schemas import WorkflowStatus, FormatOutputStep, MergeRecordsAcrossLLMsStep, ResearchMunicipalityStep
from tests.factories.official import official_factory
from tests.factories.person import person_factory
from tests.factories.workflow_context import workflow_context_factory

pytestmark = pytest.mark.unit

def test_normalize_division_with_geographic_area():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:nj/place:bayonne/government"
    division_string = "ward 3"
    division_configs = {
        "ward": {
            "has_geographic_area": True,
            "name": "ward"
        }
    }
    expected_division_ocdid = "ocd-division/country:us/state:nj/place:bayonne/ward:3"
    assert normalize_division(jurisdiction_ocdid, division_string, division_configs) == expected_division_ocdid

def test_normalize_division_without_geographic_area():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:nj/place:bayonne/government"
    division_string = "ward 3"
    division_configs = {
        "ward": {
            "has_geographic_area": False,
            "name": "ward"
        }
    }
    expected_division_ocdid = "ocd-division/country:us/state:nj/place:bayonne"
    assert normalize_division(jurisdiction_ocdid, division_string, division_configs) == expected_division_ocdid

def test_normalize_division_empty_string():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:nj/place:bayonne/government"
    division_string = None
    division_configs = {}
    expected_division_ocdid = "ocd-division/country:us/state:nj/place:bayonne"
    assert normalize_division(jurisdiction_ocdid, division_string, division_configs) == expected_division_ocdid

def test_normalize_division_unknown_key():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:nj/place:bayonne/government"
    division_string = "unknown 1"
    division_configs = {}
    expected_division_ocdid = "ocd-division/country:us/state:nj/place:bayonne"
    assert normalize_division(jurisdiction_ocdid, division_string, division_configs) == expected_division_ocdid

def test_maybe_add_fallback_url():
    person = official_factory(name="John Doe", urls=[], source_urls=["https://example.com/john_doe"])
    updated_person = maybe_add_fallback_url(person)
    assert updated_person.urls == ["https://example.com/john_doe"]

    person_with_url = official_factory(name="Jane Smith", urls=["https://example.com/jane_smith"], source_urls=["https://example.com/city_council"])
    updated_person_with_url = maybe_add_fallback_url(person_with_url)
    assert updated_person_with_url.urls == ["https://example.com/jane_smith"]

def test_generate_identities_config():
    people = [
        official_factory(name="John Doe", other_names=["Jonathan Doe"]),
        official_factory(name="Jane Smith", other_names=[]),
    ]
    identities = generate_identities_config(people)
    assert identities == {
        "John Doe": ["Jonathan Doe"],
        "Jane Smith": []
    }

def test_format_output():
    # Create mock people data
    people = [
        person_factory(name="John Doe", urls=[], source_urls=["https://example.com/john_doe"]),
        person_factory(name="Jane Smith", urls=[], source_urls=["https://example.com/jane_smith"]),
    ]

    # Create dummy data for the merge_records_across_llms_step
    merge_records_across_llms_step = MergeRecordsAcrossLLMsStep(
        people=people,
        agreement_score=85.0,  # Add the required field
        disagreements={},
        missing_people=[],
        validation_errors=[]
    )
    research_municipality_step_data = ResearchMunicipalityStep(
        government_type='mayor_council',
        people=[],
        elected_officials=[],
        notes=None
    )

    # Use the workflow_context_factory to create a mock context with dummy data
    context = workflow_context_factory({
        WorkflowStatus.RESEARCH_MUNICIPALITY: research_municipality_step_data,
        WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS: merge_records_across_llms_step,
    })

    # Call the function
    output = format_output(context)

    # Assertions
    assert isinstance(output, FormatOutputStep)
    assert len(output.officials) == 2

    # Check that URLs were added correctly
    assert output.officials[0].urls == ["https://example.com/john_doe"]
    assert output.officials[1].urls == ["https://example.com/jane_smith"]

    # Check that the config is correctly populated
    assert output.config.name == context.data.config.name
    assert len(output.config.source_urls) == 2
    assert "https://example.com/john_doe" in output.config.source_urls
    assert "https://example.com/jane_smith" in output.config.source_urls

