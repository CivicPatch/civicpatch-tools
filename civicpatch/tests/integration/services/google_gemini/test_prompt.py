import pytest
from services.google_gemini.llm import run_prompt
from services.google_gemini.prompts import municipality_officials_prompt
from jobs.people_collector.schemas import PeopleArrayLLMResponseSchema, RawLLMPerson
from typing import cast, List
from unittest.mock import patch
from pathlib import Path
import json
from tests.integration.services.common.compare_people_by_name import compare_people_by_name

pytestmark = pytest.mark.integration

TEST_REQUEST_ID = "integration_test_request_id"
TEST_JURISDICTION_ID = "ocd-jurisdiction/country:us/state:ex/place:anywhere/government"

FIXTURES_FOLDER = Path(__file__).parent.parent / "fixtures"

@pytest.mark.asyncio
async def test_run_prompt_mount_laurel_with_people():
    with open(FIXTURES_FOLDER / "mount_laurel_with_people.md", "r") as f:
        content = f.read()
    with open(FIXTURES_FOLDER / "mount_laurel_with_people_expected.json", "r") as f:
        expected_response_text = f.read()
        expected_response_json = json.loads(expected_response_text)

    prompt = municipality_officials_prompt(
        "mayor_council",
        []
    )
    response = await run_prompt(
        TEST_REQUEST_ID,
        TEST_JURISDICTION_ID,
        prompt,
        response_schema=PeopleArrayLLMResponseSchema,
        content=content,
        with_search=False
    )
    expected_response = [RawLLMPerson.model_validate(person) for person in expected_response_json]
    formatted_response = PeopleArrayLLMResponseSchema.model_validate(response)
    compare_people_by_name(
        formatted_response.people,
        expected_response,
        ignore_fields=["start_date", "end_date", "url", "image"],  # Add fields to ignore here
    )


@pytest.mark.asyncio
async def test_run_prompt_mount_laure_without_people():
    with open(FIXTURES_FOLDER / "mount_laurel_without_people.md", "r") as f:
        content = f.read()

    prompt = municipality_officials_prompt(
        "mayor_council",
        []
    )
    response = await run_prompt(
        TEST_REQUEST_ID,
        TEST_JURISDICTION_ID,
        prompt,
        response_schema=PeopleArrayLLMResponseSchema,
        content=content,
        with_search=False
    )
    formatted_response = PeopleArrayLLMResponseSchema.model_validate(response)
    assert len(formatted_response.people) == 0