"""How the law says each role is filled (plan 2's 2.13), against claims two fresh prototype runs
agreed on and the verifier supports, and repealed charters that establish nothing.

A case is one Vermont charter and the roles to ask about, plus the presiding candidates EXTRACT
also asks (`probably_not_established` when the gold lacks them, scored apart and never failed).
Every role marked `presiding`, gold or candidate, is asked in EXTRACT's one presiding question
instead of on its own; `presiding_gold_right` is the number to compare with per-role asking. Each role is asked `ASKS_PER_QUESTION`
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
from eval_utils import gather_capped, record_history, record_run, write_pass_fail_report
from runners.pipeline02_organizations_collector import sections
from runners.pipeline02_organizations_collector.role_asks import RoleAsk
from runners.pipeline02_organizations_collector.schemas import FilledBy, PresidingAnswer, RoleAnswer
from runners.pipeline02_organizations_collector.transitions.main import ASKS_PER_QUESTION, presiding_claims
from shared.schemas import SelectionMethod
from shared.utils.citation import supporting_quote
from utils import cost_utils

pytestmark = [pytest.mark.evals]

EVAL_CASES_DIR = "tests/prompts/datasets/local/governing_role"
EVALS_DIR = "tests/prompts/tests/evals/governing_role"
MODEL_NAME = "open_router"
# Charters at a time, each sending its own questions at once: all 44 together got AtlasCloud's throttling.
CASES_AT_ONCE = 4
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
    if role["expected"] == FilledBy.NOT_STATED:
        # As VERIFY keeps it: a post with no method, its quote only naming the office.
        return answer.established and answer.filled_by == FilledBy.NOT_STATED and supporting_quote(law, answer.quote, role["names"], None) is not None
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
    return _result(case, role, list(answers))


def _result(case: dict, role: dict, answers: list[RoleAnswer | None]) -> dict:
    rights = [answer is not None and is_right(case["law"], role, answer) for answer in answers]
    return {
        "role_id": role["role_id"],
        "expected": role["expected"],
        "presiding": bool(role.get("presiding")),
        "right": any(rights),
        "each_right": rights,
        "agreed": len({(answer.established, answer.filled_by) if answer else None for answer in answers}) == 1,
        "answers": [answer.model_dump(mode="json") if answer else None for answer in answers],
    }


async def ask_presiding(case: dict, roles: list[dict]) -> PresidingAnswer | None:
    question = open_router_prompts.governing_presiding_question(roles[0]["organization_name"], [(role["role_id"], role["names"]) for role in roles])
    try:
        response = await open_router_llm.run_prompt(
            _EVAL_RUN_ID,
            _LOG_JURISDICTION,
            open_router_prompts.governing_law_reader_prompt(),
            prompt_name="governing_presiding",
            response_schema=PresidingAnswer,
            content=f"{case['law']}\n\n{question}",
        )
    except Exception as error:
        print(f"Case '{case['id']}' presiding: unanswered, {type(error).__name__}: {error}")
        return None
    return PresidingAnswer.model_validate(response)


async def run_presiding(case: dict, roles: list[dict]) -> list[dict]:
    """The candidates in one question, as EXTRACT asks them; each scored as its own role."""
    if not roles:
        return []
    responses = await asyncio.gather(*[ask_presiding(case, roles) for _ in range(ASKS_PER_QUESTION)])
    asks = [RoleAsk(organization_name=role["organization_name"], role_id=role["role_id"], role_label=role["role_label"], names=role["names"]) for role in roles]
    per_ask = [presiding_claims(asks, response) if response else None for response in responses]
    return [
        _result(case, role, [claims[index].answer if claims else None for claims in per_ask])
        for index, role in enumerate(roles)
    ]


async def run_case(case: dict) -> list[dict]:
    roles = case["expected"]["roles"]
    asked_alone = [role for role in roles if not role.get("presiding")]
    alone, presiding = await asyncio.gather(
        asyncio.gather(*[run_role(case, role) for role in asked_alone]),
        run_presiding(case, [role for role in roles if role.get("presiding")]),
    )
    results = [*alone, *presiding]
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
        "presiding_gold_right": f"{sum(r['right'] for r in roles if r['presiding'])} of {sum(r['presiding'] for r in roles)}",
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
    write_pass_fail_report(
        EVALS_DIR,
        MODEL_NAME,
        run,
        cost_summary,
        total_cases=len(results_by_case),
        failed_cases=[{"case_id": case_id, "wrong_roles": roles} for case_id, roles in wrong.items() if roles],
        **summary,
        by_expected=by_expected,
        candidates_to_read={k: v for k, v in to_read.items() if v},
    )
    return summary


@pytest.mark.asyncio
async def test_governing_role_eval():
    start_time = time.time()
    results = await gather_capped([lambda case=case: run_case(case) for case in _eval_cases], limit=CASES_AT_ONCE)
    elapsed_seconds = round(time.time() - start_time, 2)
    case_results: list[list[dict]] = []
    for result in results:
        if isinstance(result, BaseException):
            raise result
        case_results.append(result)

    summary = _write_report({case["id"]: result for case, result in zip(_eval_cases, case_results)}, elapsed_seconds)
    print(f"roles right {summary['roles_right']:.0%}, one ask right {summary['single_ask_right']:.0%}, agreement {summary['agreement']:.0%}")
    print(f"presiding in one question: gold {summary['presiding_gold_right']} right; {summary['candidates_verified']} of {summary['candidates_asked']} candidates came back as a verified post, listed under candidates_to_read")
    assert summary["roles_right"] == 1.0, f"Roles answered wrong: see {EVALS_DIR}/{MODEL_NAME}-eval-report.yml"
