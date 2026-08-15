import asyncio
import time
import pytest
import pytest_asyncio
from services.open_router.llm import run_prompt as run_together_prompt
from services.open_router.prompts import relevant_page_prompt as make_together_prompt
from runners.people_collector.schemas import RelevantPageResponseSchema
from utils import cost_utils
from typing import cast
import pathlib
import yaml
import os
from accuracy import as_report
from eval_utils import PROVIDER_COMPARISON, make_provider_client, write_comparison_report
from utils.dispositions import Disposition, classify_membership, tally

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


def page_dispositions(actual: dict, expected: dict) -> dict[str, list[Disposition]]:
    """Classify one page, alongside the scores above rather than replacing them.

    `relevant_urls` is scored as recall over the expected set, so a link the fixture never
    listed costs nothing — the prompt asks for 3-20 URLs while 9 of 16 cases expect exactly
    one, and no number here can currently see that gap. Membership dispositions make the
    over-return visible without changing what the test gates on.
    """
    return {
        "relevant_urls": classify_membership(
            actual.get("relevant_urls") or [], expected.get("relevant_urls") or []
        ),
        # A boolean has no "missing" state — it is answered or it disagrees. Recording it as
        # correct/wrong_match keeps it in the same table as everything else.
        "is_relevant": [
            Disposition.correct
            if actual.get("is_relevant") == expected.get("is_relevant")
            else Disposition.wrong_match
        ],
    }


async def run_eval(model_client, case, ocdid="ocd-jurisdiction/country:us/state:tx/place:example/government"):
    """
    Runs the evaluation for a single test case.
    """
    run_prompt = model_client["run_prompt"]
    case_input = case["input"]
    expected = case["expected"]
    page_url = expected.get("page_url", "")
    jurisdiction_name = expected.get("jurisdiction_name", "")
    known_roles = expected.get("known_roles", [])
    make_prompt = model_client["make_prompt"]

    prompt = make_prompt(page_url, jurisdiction_name, known_roles)
    extra_kwargs = model_client.get("extra_kwargs", {})
    response = await run_prompt(
        "run-eval",
        ocdid,
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

    only_case = os.environ.get("EVAL_CASE")

    cases = []
    for case_dir in sorted(base.iterdir()):
        if only_case and case_dir.name != only_case:
            continue
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
    if request.param == "open_router":
        return {
            "name": "open_router",
            "run_prompt": run_together_prompt,
            "make_prompt": make_together_prompt,
            "extra_kwargs": {"model_type": "STANDARD"},
        }
    elif request.param.startswith("open_router:"):
        provider = request.param.split(":", 1)[1]
        return {
            "name": f"open_router-{provider}",
            "run_prompt": run_together_prompt,
            "make_prompt": make_together_prompt,
            "extra_kwargs": {"model_type": "STANDARD", "provider_order": [provider], "allow_fallbacks": False},
        }
    else:
        raise ValueError(f"Unknown model client: {request.param}")


def _score_case(model_client, case, case_scores, actual_output):
    thresholds = {"relevant_urls": 0.75}
    expected_page = case["expected"]["page"]
    failed = []

    actual_urls = set(actual_output.get("relevant_urls", []))
    expected_urls = set(expected_page.get("relevant_urls", []))
    score_urls = len(actual_urls & expected_urls) / len(expected_urls) if expected_urls else 1.0
    if score_urls < thresholds["relevant_urls"]:
        failed.append({
            "field": "relevant_urls",
            "expected": list(expected_urls),
            "actual": list(actual_urls),
            "score": score_urls,
            "threshold": thresholds["relevant_urls"],
        })

    if case_scores.get("is_relevant") != 1.0:
        failed.append({
            "field": "is_relevant",
            "expected": expected_page.get("is_relevant"),
            "actual": actual_output.get("is_relevant"),
            "score": case_scores.get("is_relevant"),
            "threshold": 1.0,
        })

    return failed


def _write_report(model_client, failed_cases, eval_ocdid, elapsed_seconds, dispositions=()):
    llm_costs = cost_utils.get_cost_tracker(eval_ocdid)["llm_costs"]
    cost_summary = {
        "model": llm_costs[0]["model"] if llm_costs else None,
        "elapsed_seconds": elapsed_seconds,
        "total_input_tokens": sum(c["input_tokens"] for c in llm_costs),
        "total_output_tokens": sum(c["output_tokens"] for c in llm_costs),
        "total_cost_usd": float(sum(c["total_cost"] for c in llm_costs)),
    }
    merged: dict[str, list] = {}
    for page in dispositions:
        for field, found in page.items():
            merged.setdefault(field, []).extend(found)
    accuracy = as_report({field: tally(found) for field, found in merged.items()})

    evals_dir = "tests/prompts/tests/evals/relevant_page"
    os.makedirs(evals_dir, exist_ok=True)
    report_path = os.path.join(evals_dir, f"{model_client['name']}-eval-report.yml")
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "cost_summary": cost_summary,
                "accuracy": accuracy,
                "failed_cases": failed_cases,
            },
            f,
            sort_keys=False,
        )
    print(f"Saved evaluation report to {report_path}")
    return cost_summary


def _active_providers():
    only = os.environ.get("EVAL_PROVIDER")
    return [p for p in PROVIDER_COMPARISON if not only or p.split(":", 1)[1] == only]

@pytest.mark.parametrize("model_client", _active_providers(), indirect=True)
@pytest.mark.asyncio
async def test_relevant_page_eval_with_mocked_cases(model_client, load_eval_cases):
    eval_ocdid = "ocd-jurisdiction/country:us/state:tx/place:example/government"
    start_time = time.time()
    results = await asyncio.gather(*[run_eval(model_client, case) for case in load_eval_cases])
    elapsed_seconds = round(time.time() - start_time, 2)

    failed_cases = []
    dispositions = []
    for case, (case_scores, actual_output) in zip(load_eval_cases, results):
        dispositions.append(page_dispositions(actual_output, case["expected"]["page"]))
        failed = _score_case(model_client, case, case_scores, actual_output)
        if failed:
            failed_cases.append({
                "model_client": model_client["name"],
                "case_id": case["id"],
                "failures": failed,
            })
            print(f"[{model_client['name']}] Case '{case['id']}' failed: {failed}")

    _write_report(model_client, failed_cases, eval_ocdid, elapsed_seconds, dispositions)
    assert not failed_cases, f"Some cases failed: {failed_cases}"



async def _run_provider(client, cases):
    # Provider in the place slug, not its own segment — see the note in the officials eval.
    ocdid = f"ocd-jurisdiction/country:us/state:tx/place:example_{client['name']}/government"
    start_time = time.time()
    results = await asyncio.gather(*[run_eval(client, case, ocdid) for case in cases])
    elapsed_seconds = round(time.time() - start_time, 2)

    failed_cases = []
    dispositions = []
    for case, (case_scores, actual_output) in zip(cases, results):
        dispositions.append(page_dispositions(actual_output, case["expected"]["page"]))
        failed = _score_case(client, case, case_scores, actual_output)
        if failed:
            failed_cases.append({"model_client": client["name"], "case_id": case["id"], "failures": failed})

    return client, failed_cases, ocdid, elapsed_seconds, dispositions


@pytest.mark.asyncio
async def test_provider_comparison(load_eval_cases):
    """Runs all providers concurrently and writes one report per provider."""
    clients = [make_provider_client(p, make_together_prompt) for p in PROVIDER_COMPARISON]
    results = await asyncio.gather(*[_run_provider(c, load_eval_cases) for c in clients], return_exceptions=True)

    evals_dir = "tests/prompts/tests/evals/relevant_page"
    comparison = {}
    failures = {}
    for provider_client, result in zip(clients, results):
        if isinstance(result, Exception):
            failures[provider_client["name"]] = repr(result)
            print(f"PROVIDER FAILED: {provider_client['name']}: {result!r}", flush=True)
            continue
        client, failed_cases, ocdid, elapsed_seconds, dispositions = result
        cost_summary = _write_report(client, failed_cases, ocdid, elapsed_seconds, dispositions)
        comparison[client["name"]] = {
            "elapsed_seconds": elapsed_seconds,
            "cost_usd": cost_summary["total_cost_usd"],
            "failed_cases": len(failed_cases),
            "passed_cases": len(load_eval_cases) - len(failed_cases),
        }

    write_comparison_report(evals_dir, comparison, failures)
    assert not failures, f"Providers failed: {failures}"