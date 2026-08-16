import asyncio
import time
import pathlib
import yaml
import os

import pytest

import services.google_gemini.llm as gemini_llm
from services.google_gemini.llm import FIND_JURISDICTION_URL_MODEL_FALLBACKS
import services.google_gemini.prompts as gemini_prompts
from shared.utils.url_utils import same_domain
from eval_utils import record_history, record_run
from utils import cost_utils

pytestmark = [pytest.mark.evals]

EVAL_CASES_DIR = "tests/prompts/datasets/local/find_jurisdiction_url"
EVALS_DIR = "tests/prompts/tests/evals/find_jurisdiction_url"
MODEL_NAME = "gemini"


def load_cases_from_dir(base_dir: str) -> list:
    base = pathlib.Path(base_dir)
    cases = []
    for case_dir in sorted(base.iterdir()):
        if not case_dir.is_dir():
            continue
        expected_path = case_dir / "expected.yml"
        if not expected_path.exists():
            continue
        cases.append({
            "id": case_dir.name,
            "case_path": str(case_dir),
            "expected": yaml.safe_load(expected_path.read_text()),
        })
    return cases


_eval_cases = load_cases_from_dir(EVAL_CASES_DIR)


def score_case(actual: dict, expected: dict) -> dict:
    discovered_url = actual.get("url")
    expected_url = expected.get("expected_url")
    return {
        "found": 1.0 if discovered_url is not None else 0.0,
        "url": 1.0 if discovered_url and same_domain(discovered_url, expected_url) else 0.0,
    }


async def run_eval(case):
    expected = case["expected"]
    jurisdiction_ocdid = expected["jurisdiction_ocdid"]
    prompt = gemini_prompts.find_jurisdiction_url_prompt(
        jurisdiction_ocdid,
        expected["municipality_name"],
        stale_url=expected.get("stale_url"),
    )
    response = await gemini_llm.run_prompt(
        request_id="run-eval",
        jurisdiction_ocdid=jurisdiction_ocdid,
        prompt=prompt,
        with_search=True,
        model_fallbacks=FIND_JURISDICTION_URL_MODEL_FALLBACKS,
    )
    actual = {"url": (response or {}).get("url")}
    with open(f"{case['case_path']}/{MODEL_NAME}-actual.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump(actual, f, sort_keys=False)
    return score_case(actual, expected), actual


def _sample_prompt() -> str:
    """The prompt is per-jurisdiction, so record the one the first case produced — the
    template is what changes between runs, not the substituted name."""
    case = _eval_cases[0]["expected"]
    return gemini_prompts.find_jurisdiction_url_prompt(
        case["jurisdiction_ocdid"], case.get("municipality_name", "")
    )


def _write_report(failed_cases, case_ocdids, elapsed_seconds, total_cases):
    all_costs = []
    for ocdid in case_ocdids:
        all_costs.extend(cost_utils.get_cost_tracker(ocdid)["llm_costs"])
    cost_summary = {
        "model": all_costs[0]["model"] if all_costs else None,
        "elapsed_seconds": elapsed_seconds,
        "total_input_tokens": sum(c["input_tokens"] for c in all_costs),
        "total_output_tokens": sum(c["output_tokens"] for c in all_costs),
        "total_cost_usd": float(sum(c["total_cost"] for c in all_costs)),
    }
    os.makedirs(EVALS_DIR, exist_ok=True)
    run = record_run(EVALS_DIR, _sample_prompt())
    record_history(
        EVALS_DIR,
        MODEL_NAME,
        run,
        {"cases_passed": (total_cases - len(failed_cases)) / total_cases if total_cases else None},
        cost_summary,
        {
            c["id"]: 0.0 if c["id"] in {f["case_id"] for f in failed_cases} else 1.0
            for c in _eval_cases
        },
    )
    report_path = os.path.join(EVALS_DIR, f"{MODEL_NAME}-eval-report.yml")
    with open(report_path, "w", encoding="utf-8") as f:
        # total_cases is recorded because the report cannot be read without it. This eval
        # has no provider-comparison test and so writes no comparison.yml, which is where
        # every other eval's case count lives — leaving a fully passing run indistinguishable
        # from one that ran nothing at all.
        yaml.safe_dump(
            {
                "run": run,
                "cost_summary": cost_summary,
                "total_cases": total_cases,
                "passed_cases": total_cases - len(failed_cases),
                "failed_cases": failed_cases,
            },
            f,
            sort_keys=False,
        )
    print(f"Saved evaluation report to {report_path}")
    return cost_summary


@pytest.mark.asyncio
async def test_find_jurisdiction_url_eval():
    start_time = time.time()
    results = await asyncio.gather(*[run_eval(case) for case in _eval_cases])
    elapsed_seconds = round(time.time() - start_time, 2)

    failed_cases = []
    for case, (case_scores, actual_output) in zip(_eval_cases, results):
        failures = []
        if case_scores["found"] < 1.0:
            failures.append({
                "field": "found",
                "expected": case["expected"]["expected_url"],
                "actual": None,
            })
        elif case_scores["url"] < 1.0:
            failures.append({
                "field": "url",
                "expected": case["expected"]["expected_url"],
                "actual": actual_output.get("url"),
            })
        if failures:
            failed_cases.append({"case_id": case["id"], "failures": failures})
            print(f"Case '{case['id']}' failed: {failures}")

    case_ocdids = [c["expected"]["jurisdiction_ocdid"] for c in _eval_cases]
    _write_report(failed_cases, case_ocdids, elapsed_seconds, len(_eval_cases))
    assert not failed_cases, f"Some cases failed: {failed_cases}"
