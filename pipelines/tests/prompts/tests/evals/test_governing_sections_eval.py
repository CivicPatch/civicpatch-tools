"""Which sections of a charter the model picks from its headings alone (plan 2's 2.11), against
the sections that hold each role's verified claim.

A case is one charter's heading listing, as SELECT_SECTIONS builds it. A role is covered when the
pick includes any section that supports it; a case passes when every role is, but for its known
misses (a heading that gives the model nothing to go on), which are reported, not failed. Beside coverage the
report gives the share of sections kept, since picking everything covers every role and saves
nothing. Cases are keyed to the publisher's format; the dataset grows as each format's adapter
lands. Production only asks for texts over WHOLE_TEXT_CHARS; every listing is asked here, since
any charter's headings are a fair test of the pick.
"""

import asyncio
import os
import pathlib
import re
import time

import pytest
import yaml

import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompts
from eval_utils import record_history, record_run
from runners.organizations_collector.schemas import GoverningSectionsResponse
from utils import cost_utils

pytestmark = [pytest.mark.evals]

EVAL_CASES_DIR = "tests/prompts/datasets/local/governing_sections"
EVALS_DIR = "tests/prompts/tests/evals/governing_sections"
MODEL_NAME = "open_router"
_EVAL_RUN_ID = "run-eval"
_LISTED = re.compile(r"^\s+(H\d{4}): (.*)$")


def load_cases(base_dir: str) -> list[dict]:
    cases = []
    for case_dir in sorted(pathlib.Path(base_dir).iterdir()):
        expected_path = case_dir / "expected.yml"
        if expected_path.exists():
            cases.append(
                {
                    "id": case_dir.name,
                    "case_path": str(case_dir),
                    "expected": yaml.safe_load(expected_path.read_text()),
                    "headings": (case_dir / "headings.txt").read_text(),
                }
            )
    return cases


_eval_cases = load_cases(EVAL_CASES_DIR)


def heading_by_id(listing: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in map(_LISTED.match, listing.splitlines()) if match}


def score(case: dict, picked_ids: list[str]) -> dict:
    headings = heading_by_id(case["headings"])
    picked = {headings[section_id] for section_id in picked_ids if section_id in headings}
    covering = case["expected"]["covering"]
    missed = sorted(role for role, supporting in covering.items() if not picked.intersection(supporting))
    return {
        "roles": len(covering),
        "covered": len(covering) - len(missed),
        "missed": missed,
        "unexpected_misses": [role for role in missed if role not in case["expected"].get("known_misses", {})],
        "picked": len(picked),
        "listed": len(headings),
    }


async def run_eval(case: dict) -> dict:
    expected = case["expected"]
    response = await open_router_llm.run_prompt(
        _EVAL_RUN_ID,
        expected["jurisdiction_ocdid"],
        open_router_prompts.governing_sections_prompt(),
        prompt_name="governing_sections",
        response_schema=GoverningSectionsResponse,
        content=case["headings"],
    )
    picked_ids = GoverningSectionsResponse.model_validate(response).sections
    actual = {"picked_ids": picked_ids, **score(case, picked_ids)}
    with open(f"{case['case_path']}/{MODEL_NAME}-actual.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump(actual, f, sort_keys=False)
    return actual


def _write_report(results: list[dict], elapsed_seconds: float) -> None:
    all_costs = cost_utils.get_cost_tracker(_EVAL_RUN_ID)
    cost_summary = {
        "model": all_costs[0].model if all_costs else None,
        "elapsed_seconds": elapsed_seconds,
        "total_input_tokens": sum(c.input_tokens for c in all_costs),
        "total_output_tokens": sum(c.output_tokens for c in all_costs),
        "total_cost_usd": float(cost_utils.sum_cost(all_costs)),
    }
    roles = sum(result["roles"] for result in results)
    covered = sum(result["covered"] for result in results)
    kept = sum(result["picked"] for result in results) / max(sum(result["listed"] for result in results), 1)
    by_case = {case["id"]: result for case, result in zip(_eval_cases, results)}
    os.makedirs(EVALS_DIR, exist_ok=True)
    run = record_run(EVALS_DIR, open_router_prompts.governing_sections_prompt())
    record_history(
        EVALS_DIR,
        MODEL_NAME,
        run,
        {"roles_covered": covered / max(roles, 1), "sections_kept": kept},
        cost_summary,
        {case_id: result["covered"] / max(result["roles"], 1) for case_id, result in by_case.items()},
        accuracy={},
        mismatches=None,
    )
    with open(os.path.join(EVALS_DIR, f"{MODEL_NAME}-eval-report.yml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "run": run,
                "cost_summary": cost_summary,
                "roles_covered": f"{covered}/{roles}",
                "sections_kept": round(kept, 3),
                "cases": {case_id: {k: v for k, v in result.items() if k != "picked_ids"} for case_id, result in by_case.items()},
            },
            f,
            sort_keys=False,
        )


@pytest.mark.asyncio
async def test_governing_sections_eval():
    start_time = time.time()
    results = await asyncio.gather(*[run_eval(case) for case in _eval_cases])
    elapsed_seconds = round(time.time() - start_time, 2)

    for case, result in zip(_eval_cases, results):
        if result["missed"]:
            print(f"Case '{case['id']}' missed {result['missed']} ({result['picked']} of {result['listed']} sections picked)")

    _write_report(results, elapsed_seconds)
    failed = [case["id"] for case, result in zip(_eval_cases, results) if result["unexpected_misses"]]
    assert not failed, f"Cases missing a role's section: {failed}"
