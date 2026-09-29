"""Which form of government Gemini picks for a jurisdiction, against a hand-checked answer.

Each case offers every form of its level, as open-data's country forms files list them: the
hardest version of the question, since in production a state's rules often narrow it first.
Scored by exact match, and reported per level.
"""

import asyncio
import os
import pathlib
import time

import pytest
import yaml

import services.google_gemini.llm as gemini_llm
import services.google_gemini.prompts as gemini_prompts
from eval_utils import record_history, record_run
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.id_utils import parse_jurisdiction_ocdid
from utils import cost_utils

pytestmark = [pytest.mark.evals]

EVAL_CASES_DIR = "tests/prompts/datasets/local/government_form"
EVALS_DIR = "tests/prompts/tests/evals/government_form"
MODEL_NAME = "gemini"
_EVAL_RUN_ID = "run-eval"

LOCAL_FORMS = [
    GovernmentForm.MAYOR_COUNCIL,
    GovernmentForm.COUNCIL_MANAGER,
    GovernmentForm.COMMISSION,
    GovernmentForm.TOWNSHIP_BOARD,
    GovernmentForm.OPEN_TOWN_MEETING,
    GovernmentForm.REPRESENTATIVE_TOWN_MEETING,
]
COUNTY_FORMS = [GovernmentForm.COMMISSION, GovernmentForm.COUNCIL_MANAGER, GovernmentForm.COUNTY_EXECUTIVE]


def load_cases(base_dir: str) -> list[dict]:
    cases = []
    for case_dir in sorted(pathlib.Path(base_dir).iterdir()):
        expected_path = case_dir / "expected.yml"
        if expected_path.exists():
            cases.append(
                {"id": case_dir.name, "case_path": str(case_dir), "expected": yaml.safe_load(expected_path.read_text())}
            )
    return cases


_eval_cases = load_cases(EVAL_CASES_DIR)


def prompt_for(expected: dict) -> str:
    ocdid = expected["jurisdiction_ocdid"]
    if parse_jurisdiction_ocdid(ocdid).level == JurisdictionLevel.COUNTIES:
        return gemini_prompts.county_government_form_prompt(ocdid, expected["name"], COUNTY_FORMS)
    return gemini_prompts.municipal_government_form_prompt(ocdid, expected["name"], LOCAL_FORMS)


async def run_eval(case: dict) -> dict:
    expected = case["expected"]
    response = await gemini_llm.run_prompt(
        pipeline_run_id=_EVAL_RUN_ID,
        jurisdiction_ocdid=expected["jurisdiction_ocdid"],
        prompt=prompt_for(expected),
        prompt_name="government_form",
    )
    actual = {
        "government_form": (response or {}).get("government_form"),
        "source": (response or {}).get("source"),
    }
    with open(f"{case['case_path']}/{MODEL_NAME}-actual.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump(actual, f, sort_keys=False)
    return actual


def _level(case: dict) -> str:
    return str(parse_jurisdiction_ocdid(case["expected"]["jurisdiction_ocdid"]).level)


def _write_report(failed_cases: list[dict], elapsed_seconds: float) -> None:
    all_costs = cost_utils.get_cost_tracker(_EVAL_RUN_ID)
    cost_summary = {
        "model": all_costs[0].model if all_costs else None,
        "elapsed_seconds": elapsed_seconds,
        "total_input_tokens": sum(c.input_tokens for c in all_costs),
        "total_output_tokens": sum(c.output_tokens for c in all_costs),
        # Grounded Gemini states no cost, so this is 0.0: absent, not measured as free.
        "total_cost_usd": float(cost_utils.sum_cost(all_costs)),
    }
    failed_ids = {f["case_id"] for f in failed_cases}
    by_level: dict[str, dict[str, int]] = {}
    for case in _eval_cases:
        tally = by_level.setdefault(_level(case), {"passed": 0, "total": 0})
        tally["total"] += 1
        tally["passed"] += case["id"] not in failed_ids
    os.makedirs(EVALS_DIR, exist_ok=True)
    run = record_run(EVALS_DIR, prompt_for(_eval_cases[0]["expected"]))
    record_history(
        EVALS_DIR,
        MODEL_NAME,
        run,
        {"cases_passed": (len(_eval_cases) - len(failed_cases)) / len(_eval_cases)},
        cost_summary,
        {c["id"]: 0.0 if c["id"] in failed_ids else 1.0 for c in _eval_cases},
        accuracy={},
        mismatches=None,
    )
    with open(os.path.join(EVALS_DIR, f"{MODEL_NAME}-eval-report.yml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "run": run,
                "cost_summary": cost_summary,
                "by_level": by_level,
                "total_cases": len(_eval_cases),
                "failed_cases": failed_cases,
            },
            f,
            sort_keys=False,
        )


@pytest.mark.asyncio
async def test_government_form_eval():
    start_time = time.time()
    results = await asyncio.gather(*[run_eval(case) for case in _eval_cases])
    elapsed_seconds = round(time.time() - start_time, 2)

    failed_cases = [
        {
            "case_id": case["id"],
            "expected": case["expected"]["government_form"],
            "actual": actual["government_form"],
            "source": actual["source"],
        }
        for case, actual in zip(_eval_cases, results)
        if actual["government_form"] != case["expected"]["government_form"]
    ]
    for failure in failed_cases:
        print(f"Case '{failure['case_id']}' failed: {failure}")

    _write_report(failed_cases, elapsed_seconds)
    assert not failed_cases, f"Some cases failed: {failed_cases}"
