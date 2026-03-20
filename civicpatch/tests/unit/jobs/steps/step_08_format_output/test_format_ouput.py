import pytest
from jobs.people_collector.steps.step_08_format_output.format_output import (
    format_output,
    maybe_add_fallback_url,
)
from jobs.people_collector.schemas import WorkflowStatus, FormatOutputStep, MergeRecordsAcrossLLMsStep
from tests.factories.official import official_factory
from tests.factories.person import person_factory
from tests.factories.workflow_context import workflow_context_factory

pytestmark = pytest.mark.unit

def test_maybe_add_fallback_url():
    person = official_factory(name="John Doe", urls=[], source_urls=["https://example.com/john_doe"])
    updated_person = maybe_add_fallback_url(person)
    assert updated_person.urls == ["https://example.com/john_doe"]

    person_with_url = official_factory(name="Jane Smith", urls=["https://example.com/jane_smith"], source_urls=["https://example.com/city_council"])
    updated_person_with_url = maybe_add_fallback_url(person_with_url)
    assert updated_person_with_url.urls == ["https://example.com/jane_smith"]

@pytest.mark.asyncio
async def test_format_output(httpx_mock):
    httpx_mock.add_response(
        status_code=200,
        json={"resolved_people": []}
    )

    people = [
        person_factory(name="John Doe", urls=[], source_urls=["https://example.com/john_doe"]),
        person_factory(name="Jane Smith", urls=[], source_urls=["https://example.com/jane_smith"]),
    ]

    context = workflow_context_factory({
        WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS: MergeRecordsAcrossLLMsStep(people=people),
    })

    output = await format_output(context)

    assert isinstance(output, FormatOutputStep)
    assert len(output.officials) == 2
    assert output.officials[0].urls == ["https://example.com/john_doe"]
    assert output.officials[1].urls == ["https://example.com/jane_smith"]

