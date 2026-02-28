import pytest
import pytest_asyncio
from services.openai.llm import run_prompt as run_openai_prompt
from services.openai.prompts import relevant_page_prompt as make_openai_prompt
from services.together_ai.llm import run_prompt as run_together_prompt
from services.together_ai.prompts import relevant_page_prompt as make_together_prompt
from jobs.people_collector.schemas import RelevantPageResponseSchema
from typing import cast
import pathlib
import yaml
import os

pytestmark = [pytest.mark.evals, pytest.mark.evals_relevant]

def score_page(actual: dict, expected: dict):
    """
    Scores a single page based on is_relevant and relevant_urls.
    """
    score = {}

    # is_relevant (exact match)
    score["is_relevant"] = 1.0 if actual.get("is_relevant") == expected.get("is_relevant") else 0.0

    # relevant_urls (set match)
    actual_urls = set(actual.get("relevant_urls", []))
    expected_urls = set(expected.get("relevant_urls", []))
    matching_urls = actual_urls & expected_urls
    score["relevant_urls"] = len(matching_urls) / len(expected_urls) if expected_urls else 1.0

    return score

@pytest.mark.asyncio
async def run_eval(model_client, case):
    """
    Runs the evaluation for a single test case.
    """
    run_prompt = model_client["run_prompt"]
    case_input = case["input"]
    expected = case["expected"]
    page_url = expected.get("page_url", "")
    make_prompt = model_client["make_prompt"]

    prompt = make_prompt(page_url, [])
    response = await run_prompt(
        "run-eval",
        "ocd-jurisdiction/country:us/state:tx/place:example/government",
        prompt,
        response_schema=RelevantPageResponseSchema,
        content=case_input
    )
    actual = cast(RelevantPageResponseSchema, response)
    case_path = case.get("case_path", "unknown_case")

    # Save the actual response to a file
    with open(f"{case_path}/{model_client['name']}-actual.yml", 'w', encoding='utf-8') as f:
        serialized_output = RelevantPageResponseSchema.model_dump(actual)
        yaml.safe_dump(serialized_output, f, sort_keys=False)

    # Score the single page
    return score_page(serialized_output, expected["page"])

@pytest_asyncio.fixture
def load_eval_cases(base_dir="tests/prompts/datasets/local/relevant_page"):
    """
    Loads evaluation cases from the specified directory.
    Each case contains a single page.
    """
    base = pathlib.Path(base_dir)
    cases = []

    for case_dir in sorted(base.iterdir()):
        print(f"Loading case from {case_dir}")
        if not case_dir.is_dir():
            continue

        input_path = case_dir / "input.md"
        expected_path = case_dir / "expected.yml"

        if not input_path.exists() or not expected_path.exists():
            raise ValueError(f"Missing input.md or expected.yml in {case_dir}")

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
    """
    Fixture to provide the model client for the test.
    """
    if request.param == "openai":
        return {
            "name": "openai",
            "run_prompt": run_openai_prompt,
            "make_prompt": make_openai_prompt,
        }
    elif request.param == "together_ai":
        return {
            "name": "together_ai",
            "run_prompt": run_together_prompt,
            "make_prompt": make_together_prompt,
        }
    else:
        raise ValueError(f"Unknown model client: {request.param}")

@pytest.mark.parametrize("model_client", ["openai", "together_ai"], indirect=True)
@pytest.mark.asyncio
async def test_relevant_page_eval_with_mocked_cases(model_client, load_eval_cases):
    """
    Test each case with a single RelevantPageResponseSchema.
    """
    thresholds = {
        "relevant_urls": 0.85,  # Keep threshold for relevant_urls
    }

    failed_cases = []
    for case in load_eval_cases:
        print(f"Running evaluation for case: {case['id']}")
        case_scores = await run_eval(model_client, case)

        # Check thresholds
        failed = []
        for key, threshold in thresholds.items():
            actual_score = case_scores.get(key, 1.0)
            print(f"  {key}: actual={actual_score:.3f}, expected>={threshold}")
            if actual_score < threshold:
                failed.append(f"{key}: actual={actual_score:.3f}, expected>={threshold}")

        # Handle boolean comparison for is_relevant
        if case_scores.get("is_relevant") != 1.0:  # 1.0 represents a match (true == true)
            failed.append(f"is_relevant: actual={case_scores.get('is_relevant')}, expected=true")

        if failed:
            failed_cases.append({
                "model_client": model_client["name"],
                "case_id": case["id"],
                "failures": failed
            })
            print(f"[{model_client['name']}] Case '{case['id']}' failed: {', '.join(failed)}")

    # Write full report to file
    evals_dir = "tests/prompts/tests/evals/relevant_page"
    os.makedirs(evals_dir, exist_ok=True)
    report_path = os.path.join(evals_dir, f"{model_client['name']}-eval-report.yml")
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "failed_cases": failed_cases
        }, f, sort_keys=False)
    print(f"Saved evaluation report to {report_path}")

    # Assert no failed cases
    assert not failed_cases, f"Some cases failed: {failed_cases}"