import pytest
import pytest_asyncio
from utils import merge_utils
from services.openai.llm import run_prompt as run_openai_prompt
from services.openai.prompts import municipality_officials_prompt as make_openai_prompt
from services.google_gemini.llm import run_prompt as run_gemini_prompt 
from services.google_gemini.prompts import municipality_officials_prompt as make_gemini_prompt
from jobs.people_collector.schemas import PeopleArrayLLMResponseSchema, RawLLMPerson
import phonenumbers
from typing import cast, List
import pathlib
import yaml
from tests.utils import find_person_by_name

pytestmark = pytest.mark.evals

def score_cases(actual: List[RawLLMPerson], expected: List[RawLLMPerson]):
    scores = []
    for e_person in expected:
        a_person = find_person_by_name(actual, e_person.name)
        if a_person:
            score = score_case(a_person, e_person)
        else:
            score = {
                "name": 0.0,
                "roles": 0.0,
                "divisions": 0.0,
                "email": 0.0,
                "phone": 0.0,
                "url": 0.0
            }
        scores.append(score)
    return scores

def score_case(actual: RawLLMPerson, expected: RawLLMPerson):
    score = {}

    # name (normalized)
    score["name"] = merge_utils.normalize_name(actual.name) == merge_utils.normalize_name(expected.name) and 1.0 or 0.0

    # roles (set match)
    score["roles"] = len(set(actual.roles) & set(expected.roles)) / len(expected.roles)

    if not expected.divisions:  # Check if the list is empty
        score["divisions"] = 1.0
    else:
        score["divisions"] = len(set(actual.divisions) & set(expected.divisions)) / len(expected.divisions)

    # email
    score["email"] = 1.0 if actual.email == expected.email else 0.0

    # phone
    actual_phone_parsed = phonenumbers.parse(actual.phone, "US") if actual.phone else None
    expected_phone_parsed = phonenumbers.parse(expected.phone, "US") if expected.phone else None
    print("actual:", actual_phone_parsed)
    print("expected:", expected_phone_parsed)
    score["phone"] = 1.0 if actual_phone_parsed == expected_phone_parsed else 0.0

    score["url"] = 1.0 if actual.url == expected.url else 0.0

    return score

def aggregate(scores):
    """
    Aggregates the scores from all test cases into a single report.
    Each key in the score dictionary is averaged across all cases.
    If there are multiple people in a case, their scores are averaged first.
    """
    if not scores:
        return {}

    # Aggregate scores for each case
    case_aggregates = []
    for case_scores in scores:
        if not case_scores:
            continue
        case_aggregate = {}
        for key in case_scores[0].keys():
            case_aggregate[key] = sum(score[key] for score in case_scores) / len(case_scores)
        case_aggregates.append(case_aggregate)

    # Aggregate scores across all cases
    if not case_aggregates:
        return {}

    final_aggregate = {}
    for key in case_aggregates[0].keys():
        final_aggregate[key] = sum(case[key] for case in case_aggregates) / len(case_aggregates)

    return final_aggregate

@pytest.mark.asyncio
async def run_eval(model_client, cases):
    scores = []

    for case in cases:
        run_prompt = model_client["run_prompt"]
        make_prompt = model_client["make_prompt"] 

        case_input = case["input"]
        prompt = make_prompt(
            "mayor_council",
            []  # people_hint
        )
        # Await the run_prompt coroutine
        response = await run_prompt(
            "run-eval",
            "ocd-jurisdiction/country:us/state:tx/place:austin/government",
            prompt,
            response_schema=PeopleArrayLLMResponseSchema,
            content=case_input
        )
        expected = [RawLLMPerson(**person) for person in case["expected"]["people"]] 
        actual = cast(PeopleArrayLLMResponseSchema, response)
        case_path = case.get("case_path", "unknown_case")
        with open(f"{case_path}/{model_client["name"]}-actual.yml", 'w', encoding='utf-8') as f:
            serialized_output = PeopleArrayLLMResponseSchema.model_dump(actual)
            yaml_output = yaml.safe_dump(serialized_output, sort_keys=False)
            f.write(yaml_output)

        # Calculate scores for all people in the case
        case_scores = score_cases(actual.people, expected)
        scores.append(case_scores)

    # Aggregate scores at both levels
    return aggregate(scores)

@pytest_asyncio.fixture
def load_eval_cases(base_dir="tests/prompts/datasets/local"):
    base = pathlib.Path(base_dir)
    cases = []

    for case_dir in sorted(base.iterdir()):
        print(f"Loading case from {case_dir}")
        if not case_dir.is_dir():
            continue

        input_path = case_dir / "input.md"
        expected_path = case_dir / "expected.yml"

        if not input_path.exists() or not expected_path.exists():
            raise ValueError(f"Missing input.txt or expected.yml in {case_dir}")

        with open(expected_path, 'r', encoding='utf-8') as f:
            expected_content = yaml.safe_load(f)

        case = {
            "id": case_dir.name,
            "case_path": str(case_dir),
            "input": input_path.read_text(encoding="utf-8"),
            "expected": expected_content,
        }

        cases.append(case)

    return cases

@pytest_asyncio.fixture
async def model_client(request):
    if request.param == "openai":
        return {
            "name": "openai",
            "run_prompt": run_openai_prompt,
            "make_prompt": make_openai_prompt,
        }
    elif request.param == "gemini":
        return {
            "name": "gemini",
            "run_prompt": run_gemini_prompt,
            "make_prompt": make_gemini_prompt,
        }
    else:
        raise ValueError(f"Unknown model client: {request.param}")

@pytest.mark.parametrize("model_client", ["openai", "gemini"], indirect=True)
@pytest.mark.asyncio
async def test_eval_with_mocked_cases(model_client, load_eval_cases):
    report = await run_eval(model_client, load_eval_cases)
    print("Final aggregated report:", report)

    # Same rubric, per-model thresholds (tune these)
    assert report["name"] >= 0.95
    assert report["roles"] >= 0.90
    assert report["divisions"] >= 0.85
    assert report["email"] >= 0.90
    assert report["phone"] >= 0.90
    assert report["url"] >= 0.70
