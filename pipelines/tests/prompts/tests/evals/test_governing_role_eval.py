"""How the law says each role is filled (plan 2's 2.13), against claims two fresh prototype runs
agreed on and the verifier supports, and repealed charters that establish nothing.

A case is one Vermont charter and the roles to ask about, plus the presiding candidates EXTRACT
also asks (`probably_not_established` when the gold lacks them, scored apart and never failed). Each role is asked `ASKS_PER_QUESTION`
times, as EXTRACT does, and is right when any answer gives the expected method with a quote
shared's verifier supports, or, expected "not_established", says the office is not established.
Agreement between a role's answers is reported beside accuracy: the open "list every role" ask
agreed 56% of the time, the number this design is meant to beat. A charter over
WHOLE_TEXT_CHARS is read as its keyword sections, the pick's free and repeatable stand-in.
"""

import asyncio
import os
import pathlib
import time

import pytest
import yaml

import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompts
from eval_utils import record_history, record_run
from runners.pipeline02_organizations_collector import sections
from runners.pipeline02_organizations_collector.schemas import FilledBy, RoleAnswer
from runners.pipeline02_organizations_collector.transitions.main import ASKS_PER_QUESTION
from shared.schemas import SelectionMethod
from shared.utils.citation import supporting_quote
from utils import cost_utils

pytestmark = [pytest.mark.evals]

EVAL_CASES_DIR = "tests/prompts/datasets/local/governing_role"
EVALS_DIR = "tests/prompts/tests/evals/governing_role"
MODEL_NAME = "open_router"
_EVAL_RUN_ID = "run-eval"
NOT_ESTABLISHED = "not_established"
# A presiding candidate the gold lacks: listed for a person when it verifies, never failed on.
PROBABLY_NOT_ESTABLISHED = "probably_not_established"
# `run_prompt` names its log by jurisdiction; the cases are charters, so one Vermont id for all.
_LOG_JURISDICTION = "ocd-jurisdiction/country:us/state:vt/place:eval/government"


def load_cases(base_dir: str) -> list[dict]:
    cases = []
    for case_dir in sorted(pathlib.Path(base_dir).iterdir()):
        expected_path = case_dir / "expected.yml"
        if expected_path.exists():
            expected = yaml.safe_load(expected_path.read_text())
            cases.append({"id": case_dir.name, "case_path": str(case_dir), "expected": expected, "law": _law((case_dir / "input.md").read_text(), expected["source_url"])})
    return cases


def _law(text: str, source_url: str) -> str:
    if sections.fits_whole(text):
        return text
    found = sections.split_sections([sections.GoverningLawPage(id="eval", source_url=source_url, text=text)])
    return "# Charter\n\n" + sections.joined(sections.keyword_sections(found))


_eval_cases = load_cases(EVAL_CASES_DIR)


def is_verified_post(law: str, role: dict, answer: RoleAnswer) -> bool:
    if not answer.established or answer.filled_by == FilledBy.NOT_STATED:
        return False
    return supporting_quote(law, answer.quote, role["names"], SelectionMethod(answer.filled_by.value)) is not None


def is_right(law: str, role: dict, answer: RoleAnswer) -> bool:
    if role["expected"] == NOT_ESTABLISHED:
        return not answer.established
    if role["expected"] == PROBABLY_NOT_ESTABLISHED:
        return not is_verified_post(law, role, answer)
    return answer.filled_by.value == role["expected"] and is_verified_post(law, role, answer)


async def ask(case: dict, role: dict) -> RoleAnswer | None:
    """None when the call still failed after `run_prompt`'s retries, scored wrong, as EXTRACT
    leaves such a role unanswered."""
    question = open_router_prompts.governing_role_question(role["role_label"], role["organization_name"])
    try:
        response = await open_router_llm.run_prompt(
            _EVAL_RUN_ID,
            _LOG_JURISDICTION,
            open_router_prompts.governing_law_reader_prompt(),
            prompt_name="governing_role",
            response_schema=RoleAnswer,
            content=f"{case['law']}\n\n{question}",
        )
    except Exception as error:
        print(f"Case '{case['id']}' {role['role_id']}: unanswered, {type(error).__name__}: {error}")
        return None
    return RoleAnswer.model_validate(response)


async def run_role(case: dict, role: dict) -> dict:
    answers = await asyncio.gather(*[ask(case, role) for _ in range(ASKS_PER_QUESTION)])
    rights = [answer is not None and is_right(case["law"], role, answer) for answer in answers]
    return {
        "role_id": role["role_id"],
        "expected": role["expected"],
        "right": any(rights),
        "each_right": rights,
        "agreed": len({(answer.established, answer.filled_by) if answer else None for answer in answers}) == 1,
        "answers": [answer.model_dump(mode="json") if answer else None for answer in answers],
    }


async def run_case(case: dict) -> list[dict]:
    results = await asyncio.gather(*[run_role(case, role) for role in case["expected"]["roles"]])
    with open(f"{case['case_path']}/{MODEL_NAME}-actual.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump(results, f, sort_keys=False, allow_unicode=True)
    return results


def _case_right(results: list[dict]) -> float:
    return sum(r["right"] for r in results) / len(results)


def _write_report(results_by_case: dict[str, list[dict]], elapsed_seconds: float) -> dict:
    all_costs = cost_utils.get_cost_tracker(_EVAL_RUN_ID)
    every_role = [result for results in results_by_case.values() for result in results]
    roles = [result for result in every_role if result["expected"] != PROBABLY_NOT_ESTABLISHED]
    candidates = [result for result in every_role if result["expected"] == PROBABLY_NOT_ESTABLISHED]
    by_expected: dict[str, dict[str, int]] = {}
    for result in roles:
        tally = by_expected.setdefault(result["expected"], {"right": 0, "total": 0})
        tally["total"] += 1
        tally["right"] += result["right"]
    summary = {
        "roles_right": sum(result["right"] for result in roles) / len(roles),
        "single_ask_right": sum(sum(result["each_right"]) for result in roles) / (len(roles) * ASKS_PER_QUESTION),
        "agreement": sum(result["agreed"] for result in roles) / len(roles),
        "candidates_asked": len(candidates),
        "candidates_verified": sum(not result["right"] for result in candidates),
    }
    cost_summary = {
        "model": all_costs[0].model if all_costs else None,
        "elapsed_seconds": elapsed_seconds,
        "total_input_tokens": sum(c.input_tokens for c in all_costs),
        "total_cached_input_tokens": sum(c.cached_input_tokens for c in all_costs),
        "total_output_tokens": sum(c.output_tokens for c in all_costs),
        "total_cost_usd": float(cost_utils.sum_cost(all_costs)),
    }
    os.makedirs(EVALS_DIR, exist_ok=True)
    run = record_run(EVALS_DIR, open_router_prompts.governing_law_reader_prompt())
    record_history(
        EVALS_DIR,
        MODEL_NAME,
        run,
        summary,
        cost_summary,
        {case_id: _case_right([r for r in results if r["expected"] != PROBABLY_NOT_ESTABLISHED]) for case_id, results in results_by_case.items()},
        accuracy={},
        mismatches=None,
    )
    wrong = {case_id: [r["role_id"] for r in results if not r["right"] and r["expected"] != PROBABLY_NOT_ESTABLISHED] for case_id, results in results_by_case.items()}
    to_read = {
        case_id: [
            {"role_id": r["role_id"], "answers": [a for a in r["answers"] if a and a["established"]]}
            for r in results if not r["right"] and r["expected"] == PROBABLY_NOT_ESTABLISHED
        ]
        for case_id, results in results_by_case.items()
    }
    with open(os.path.join(EVALS_DIR, f"{MODEL_NAME}-eval-report.yml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "run": run, "cost_summary": cost_summary, **summary, "by_expected": by_expected,
                "wrong": {k: v for k, v in wrong.items() if v},
                "candidates_to_read": {k: v for k, v in to_read.items() if v},
            },
            f,
            sort_keys=False,
        )
    return summary


@pytest.mark.asyncio
async def test_governing_role_eval():
    start_time = time.time()
    results = await asyncio.gather(*[run_case(case) for case in _eval_cases])
    elapsed_seconds = round(time.time() - start_time, 2)

    summary = _write_report({case["id"]: result for case, result in zip(_eval_cases, results)}, elapsed_seconds)
    print(f"roles right {summary['roles_right']:.0%}, one ask right {summary['single_ask_right']:.0%}, agreement {summary['agreement']:.0%}")
    print(f"presiding candidates: {summary['candidates_verified']} of {summary['candidates_asked']} came back as a verified post, listed under candidates_to_read")
    assert summary["roles_right"] == 1.0, f"Roles answered wrong: see {EVALS_DIR}/{MODEL_NAME}-eval-report.yml"
