"""The research prompt: given its government-form organizations as a hint, does
Gemini return each official with the right body (organization)?

Cold-start only, Gemini grounded. `body` resolves Gemini's answer the way the
pipeline does (`parse_label_preferring` then `_organization_for`), so the gate
is "did the right body win", not "did Gemini echo the hinted name". `name_match`
reports how often the raw string names one of our organizations; roster drift
lowers `recall` (reported, not gated). A case with no expected `organization`
(no form known) checks recall only.
"""

import asyncio
import os
import pathlib
import time

import pytest
import yaml
from accuracy import build_eval_taxonomy
from eval_utils import record_history, record_run, write_pass_fail_report

import services.google_gemini.llm as gemini_llm
import services.google_gemini.prompts as gemini_prompts
from shared.schemas import KnownOrganization
from shared.utils.label_parser import parse_label_preferring
from utils import cost_utils

pytestmark = [pytest.mark.evals]

EVAL_CASES_DIR = "tests/prompts/datasets/local/research_municipality"
EVALS_DIR = "tests/prompts/tests/evals/research_municipality"
MODEL_NAME = "gemini"
# One run for the whole eval: no provider comparison, so every case shares a tally.
_EVAL_RUN_ID = "run-eval"


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


def _organizations(expected: dict) -> list[KnownOrganization]:
    return [
        KnownOrganization(
            id=organization["name"].strip().casefold().replace(" ", "-"),
            name=organization["name"],
            role_labels=organization.get("role_labels", []),
            meta_is_default=organization.get("meta_is_default", False),
        )
        for organization in expected.get("organizations", [])
    ]


def _prompt(expected: dict) -> str:
    return gemini_prompts.research_municipality_prompt(
        expected["jurisdiction_ocdid"], expected["name"], _organizations(expected)
    )


def _resolved_organization(
    researched: str,
    role_label: str,
    organizations: list[KnownOrganization],
    default: KnownOrganization,
) -> KnownOrganization:
    """The body research's answer files into; mirrors `_organization_for` in
    the pipeline."""
    for organization in organizations:
        if organization.name.casefold() == researched.strip().casefold():
            return organization
    for organization in organizations:
        if role_label in organization.role_labels:
            return organization
    return default


def score_case(actual: dict, expected: dict) -> dict:
    """`body` and `name_match` over matched officials; `recall` over the
    whole roster."""
    organizations = _organizations(expected)
    default = next(
        (o for o in organizations if o.meta_is_default), organizations[0]
    )
    post_roles = [label for o in organizations for label in o.role_labels]
    taxonomy = build_eval_taxonomy()
    known_names = {o.name.strip().casefold() for o in organizations}
    returned = {
        (person.get("name") or "").strip().casefold(): person
        for person in actual.get("people", [])
    }
    expected_people = expected.get("people", [])
    matched = 0
    name_matched = 0
    resolved = 0
    correct = 0
    for person in expected_people:
        got = returned.get(person["name"].strip().casefold())
        if got is None:
            continue
        matched += 1
        got_org = (got.get("organization") or "").strip()
        if got_org.casefold() in known_names:
            name_matched += 1
        expected_body = person.get("organization")
        if not expected_body:
            continue
        parsed = parse_label_preferring(got.get("label") or "", taxonomy, post_roles)
        if not parsed.role:
            continue
        resolved += 1
        resolved_name = _resolved_organization(
            got_org, parsed.role, organizations, default
        ).name.casefold()
        if resolved_name == expected_body.strip().casefold():
            correct += 1
    has_bodies = any(person.get("organization") for person in expected_people)
    body = correct / resolved if resolved else (1.0 if not has_bodies else 0.0)
    return {
        "body": body,
        "name_match": 1.0 if matched == 0 else name_matched / matched,
        "recall": 0.0 if not expected_people else matched / len(expected_people),
    }


async def run_eval(case):
    expected = case["expected"]
    response = await gemini_llm.run_prompt(
        pipeline_run_id=_EVAL_RUN_ID,
        jurisdiction_ocdid=expected["jurisdiction_ocdid"],
        prompt=_prompt(expected),
        prompt_name="research_municipality",
    )
    actual = {"people": (response or {}).get("people", [])}
    actual_path = f"{case['case_path']}/{MODEL_NAME}-actual.yml"
    with open(actual_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(actual, f, sort_keys=False)
    return score_case(actual, expected), actual


def _sample_prompt() -> str:
    return _prompt(_eval_cases[0]["expected"])


def _write_report(failed_cases, elapsed_seconds, total_cases, body, name_match, recall):
    all_costs = cost_utils.get_cost_tracker(_EVAL_RUN_ID)
    cost_summary = {
        "model": all_costs[0].model if all_costs else None,
        "elapsed_seconds": elapsed_seconds,
        "total_input_tokens": sum(c.input_tokens for c in all_costs),
        "total_output_tokens": sum(c.output_tokens for c in all_costs),
        # Grounded Gemini states no cost, so this is 0.0 — absent, not measured as free.
        "total_cost_usd": float(cost_utils.sum_cost(all_costs)),
    }
    os.makedirs(EVALS_DIR, exist_ok=True)
    run = record_run(EVALS_DIR, _sample_prompt())
    failed_ids = {f["case_id"] for f in failed_cases}
    passed = total_cases - len(failed_cases)
    record_history(
        EVALS_DIR,
        MODEL_NAME,
        run,
        {
            "cases_passed": passed / total_cases if total_cases else None,
            "body": body,
            "name_match": name_match,
            "recall": recall,
        },
        cost_summary,
        {c["id"]: 0.0 if c["id"] in failed_ids else 1.0 for c in _eval_cases},
        accuracy={},
        mismatches=None,
    )
    report_path = write_pass_fail_report(EVALS_DIR, MODEL_NAME, run, cost_summary, total_cases, failed_cases)
    print(f"Saved evaluation report to {report_path}")
    return cost_summary


@pytest.mark.asyncio
async def test_research_municipality_eval():
    start_time = time.time()
    results = await asyncio.gather(*[run_eval(case) for case in _eval_cases])
    elapsed_seconds = round(time.time() - start_time, 2)

    failed_cases = []
    body_scores = []
    name_match_scores = []
    recall_scores = []
    for case, (case_scores, actual_output) in zip(_eval_cases, results, strict=True):
        body_scores.append(case_scores["body"])
        name_match_scores.append(case_scores["name_match"])
        recall_scores.append(case_scores["recall"])
        failures = []
        if case_scores["recall"] == 0.0:
            failures.append({
                "field": "people",
                "expected": "any of the expected officials",
                "actual": actual_output.get("people"),
            })
        elif case_scores["body"] < 1.0:
            failures.append({
                "field": "organization",
                "expected": "each official's body",
                "actual": actual_output.get("people"),
            })
        if failures:
            failed_cases.append({"case_id": case["id"], "failures": failures})
            print(f"Case '{case['id']}' failed: {failures}")

    mean_body = sum(body_scores) / len(body_scores) if body_scores else None
    mean_name_match = (
        sum(name_match_scores) / len(name_match_scores) if name_match_scores else None
    )
    mean_recall = sum(recall_scores) / len(recall_scores) if recall_scores else None
    _write_report(
        failed_cases,
        elapsed_seconds,
        len(_eval_cases),
        mean_body,
        mean_name_match,
        mean_recall,
    )
    assert not failed_cases, f"Some cases failed: {failed_cases}"
