import pytest
import pytest_asyncio
from services.google_gemini.llm import run_prompt as run_gemini_prompt
from services.google_gemini.prompts import relevant_page_prompt as make_gemini_prompt
from services.together_ai.llm import run_prompt as run_together_prompt
from services.together_ai.prompts import relevant_page_prompt as make_together_prompt
from jobs.people_collector.schemas import RelevantPageResponseSchema
from typing import cast
import pathlib
import yaml
import os

pytestmark = [pytest.mark.evals_relevant]

EVAL_CASES_DIR = "tests/prompts/datasets/local/relevant_page"


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


async def run_eval(model_client, case):
    """
    Runs the evaluation for a single test case.
    """
    run_prompt = model_client["run_prompt"]
    case_input = case["input"]
    expected = case["expected"]
    page_url = expected.get("page_url", "")
    make_prompt = model_client["make_prompt"]

    prompt = make_prompt(page_url)
    extra_kwargs = model_client.get("extra_kwargs", {})
    response = await run_prompt(
        "run-eval",
        "ocd-jurisdiction/country:us/state:tx/place:example/government",
        prompt,
        response_schema=RelevantPageResponseSchema,
        content=case_input,
        **extra_kwargs,
    )
    actual = cast(RelevantPageResponseSchema, response)
    case_path = case.get("case_path", "unknown_case")

    # Save the actual response to a file
    with open(f"{case_path}/{model_client['name']}-actual.yml", 'w', encoding='utf-8') as f:
        serialized_output = RelevantPageResponseSchema.model_dump(actual)
        yaml.safe_dump(serialized_output, f, sort_keys=False)

    # Return both score and actual output
    return score_page(serialized_output, expected["page"]), serialized_output


def load_cases_from_dir(base_dir: str) -> list:
    """
    Loads evaluation cases from the specified directory.
    Each case contains a single page.
    """
    base = pathlib.Path(base_dir)
    if not base.exists():
        raise FileNotFoundError(f"Eval cases directory not found: {base_dir}")

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

        cases.append({
            "id": case_dir.name,
            "case_path": str(case_dir),
            "input": input_path.read_text(encoding="utf-8"),
            "expected": expected_content,
        })

    return cases


# Load cases at collection time so pytest can see them for parametrization
_eval_cases = load_cases_from_dir(EVAL_CASES_DIR)


@pytest.fixture
def load_eval_cases():
    return _eval_cases


@pytest_asyncio.fixture
async def model_client(request):
    if request.param == "google_gemini":
        return {
            "name": "google_gemini",
            "run_prompt": run_gemini_prompt,
            "make_prompt": make_gemini_prompt,
            "extra_kwargs": {},
        }
    elif request.param == "together_ai":
        return {
            "name": "together_ai",
            "run_prompt": run_together_prompt,
            "make_prompt": make_together_prompt,
            "extra_kwargs": {"model_type": "STANDARD"},
        }
    else:
        raise ValueError(f"Unknown model client: {request.param}")


@pytest.mark.parametrize("model_client", ["google_gemini", "together_ai"], indirect=True)
@pytest.mark.asyncio
async def test_relevant_page_eval_with_mocked_cases(model_client, load_eval_cases):
    """
    Test each case with a single RelevantPageResponseSchema.
    """
    thresholds = {
        "relevant_urls": 0.75,
    }

    failed_cases = []
    for case in load_eval_cases:
        print(f"Running evaluation for case: {case['id']}")
        (case_scores, actual_output) = await run_eval(model_client, case)
        expected_page = case["expected"]["page"]
        failed = []

        # relevant_urls comparison
        actual_urls = set(actual_output.get("relevant_urls", []))
        expected_urls = set(expected_page.get("relevant_urls", []))
        score_urls = len(actual_urls & expected_urls) / len(expected_urls) if expected_urls else 1.0
        if score_urls < thresholds["relevant_urls"]:
            failed.append({
                "field": "relevant_urls",
                "expected": list(expected_urls),
                "actual": list(actual_urls),
                "score": score_urls,
                "threshold": thresholds["relevant_urls"]
            })

        # is_relevant comparison
        if case_scores.get("is_relevant") != 1.0:
            failed.append({
                "field": "is_relevant",
                "expected": expected_page.get("is_relevant"),
                "actual": actual_output.get("is_relevant"),
                "score": case_scores.get("is_relevant"),
                "threshold": 1.0
            })

        if failed:
            failed_cases.append({
                "model_client": model_client["name"],
                "case_id": case["id"],
                "failures": failed
            })
            print(f"[{model_client['name']}] Case '{case['id']}' failed: {failed}")

    # Write full report to file
    evals_dir = "tests/prompts/tests/evals/relevant_page"
    os.makedirs(evals_dir, exist_ok=True)
    report_path = os.path.join(evals_dir, f"{model_client['name']}-eval-report.yml")
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "failed_cases": failed_cases
        }, f, sort_keys=False)
    print(f"Saved evaluation report to {report_path}")

    assert not failed_cases, f"Some cases failed: {failed_cases}"