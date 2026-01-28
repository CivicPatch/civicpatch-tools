# tests/contract/test_openai_contract.py
import pytest
from pathlib import Path
from services.openai.llm import run_prompt as run_openai_prompt
from services.openai.prompts import municipality_officials_prompt as make_openai_prompt
from jobs.people_collector.schemas import PeopleArrayLLMResponseSchema
import yaml

pytestmark = pytest.mark.contracts

def test_openai_contract_matches_expected_yaml():
    case_dir = Path("tests/prompts/datasets/local/austin_council")

    prompt = make_openai_prompt(
        "mayor_council",
        []
    )
    input_text = (case_dir / "input.md").read_text(encoding="utf-8")
    expected = yaml.safe_load((case_dir / "expected.yaml").read_text(encoding="utf-8"))

    actual = run_openai_prompt(
        "contract-test",
        "jurisdiction-ocdid",
        prompt,
        response_schema=PeopleArrayLLMResponseSchema,
        content=input_text
    )
    print("Actual output:", actual)

    assert "people" in actual

    # compare length of people

    # for each person in expected, find matching person in actual by name

def find_person_by_name(people, name):
    for person in people:
        if person.name == name:
            return person
    return None