"""Does `page_covers_organization_prompt` say which bodies a page carries people for.

One question per (page, body), because that is how the pipeline asks it: a wrong answer is
silent either way, and neither the heuristics nor the extraction can catch it. A false negative
drops a body's extraction on a page that did carry it, and the records simply never appear; a
false positive pays for an extraction that returns nobody.

The cases are real pages from `data_source`, and four of the ten answers are "no" on a page that
looks like a yes: navigation naming the other body, an agenda page about a body that lists none
of its people, and a homepage whose news headlines name the mayor.

Run with: mise run evalsc
"""

import asyncio
from functools import partial
import os
import pathlib
import time
from typing import cast

import pytest
import yaml
from accuracy import as_report
from eval_utils import (
    PROVIDER_COMPARISON,
    gather_capped,
    make_provider_client,
    record_history,
    record_provider_failure,
    record_run,
    write_comparison_report,
)
from runners.people_collector.schemas import OrganizationCoverageResponseSchema
from services.open_router.prompts import page_covers_organization_prompt
from utils import cost_utils
from utils.dispositions import Disposition, tally

pytestmark = [pytest.mark.evals_relevant]

EVAL_CASES_DIR = "tests/prompts/datasets/local/page_covers"
EVALS_DIR = "tests/prompts/tests/evals/page_covers"


def _eval_run_id(provider_name: str) -> str:
    return f"run-eval-covers-{provider_name}"


def load_cases_from_dir(base_dir: str) -> list:
    base = pathlib.Path(base_dir)
    if not base.exists():
        raise FileNotFoundError(f"Eval cases directory not found: {base_dir}")
    only_case = os.environ.get("EVAL_CASE")

    cases = []
    for case_dir in sorted(base.iterdir()):
        if not case_dir.is_dir() or (only_case and case_dir.name != only_case):
            continue
        input_path = case_dir / "input.md"
        expected_path = case_dir / "expected.yml"
        if not input_path.exists() or not expected_path.exists():
            raise ValueError(f"Missing input.md or expected.yml in {case_dir}")
        cases.append({
            "id": case_dir.name,
            "case_path": str(case_dir),
            "input": input_path.read_text(encoding="utf-8"),
            "expected": yaml.safe_load(expected_path.read_text(encoding="utf-8")),
        })
    return cases


_eval_cases = load_cases_from_dir(EVAL_CASES_DIR)


@pytest.fixture
def load_eval_cases():
    return _eval_cases


async def run_eval(model_client, case, ocdid) -> tuple[dict, dict]:
    """One call per body on this page. Returns the answers and which of them were wrong.

    A call that fails after its retries is recorded as a wrong answer for that body rather than
    raised: a provider timing out on page four should not discard the three pages already paid
    for, and a run that returns nothing is the most expensive outcome available.
    """
    expected = case["expected"]
    answers = await gather_capped([
        partial(
            model_client["run_prompt"],
            _eval_run_id(model_client["name"]),
            ocdid,
            page_covers_organization_prompt(
                organization["name"],
                organization.get("posts", []),
                expected.get("jurisdiction_name", ""),
            ),
            prompt_name="page_covers_organization",
            response_schema=OrganizationCoverageResponseSchema,
            content=case["input"],
            **model_client.get("extra_kwargs", {}),
        )
        for organization in expected["organizations"]
    ])
    actual = {
        organization["name"]: (
            f"error: {answer!r}"
            if isinstance(answer, BaseException)
            else cast(OrganizationCoverageResponseSchema, answer).covers
        )
        for organization, answer in zip(expected["organizations"], answers)
    }
    with open(f"{case['case_path']}/{model_client['name']}-actual.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"covers": actual}, f, sort_keys=False)
    wrong = {
        name: {"expected": expected["covers"][name], "actual": answered}
        for name, answered in actual.items()
        if expected["covers"][name] != answered
    }
    return actual, wrong


def _dispositions(actual: dict, expected: dict) -> list[Disposition]:
    """A boolean is answered or it disagrees, so there is no missing state to record."""
    return [
        Disposition.correct if expected[name] == answered else Disposition.wrong_match
        for name, answered in actual.items()
    ]


async def _run_provider(client, cases):
    ocdid = f"ocd-jurisdiction/country:us/state:tx/place:example_{client['name']}/government"
    start_time = time.time()
    # Per case as well as per body: whatever survives is worth reporting, and a provider that
    # dies on one page still has an answer for the others.
    gathered = await gather_capped([partial(run_eval, client, case, ocdid) for case in cases])
    results = [
        ({}, {"run": {"expected": "an answer", "actual": f"error: {r!r}"}})
        if isinstance(r, BaseException)
        else r
        for r in gathered
    ]
    elapsed_seconds = round(time.time() - start_time, 2)

    failed_cases = []
    found: list[Disposition] = []
    mismatches: dict[str, list[dict]] = {}
    for case, (actual, wrong) in zip(cases, results):
        found.extend(_dispositions(actual, case["expected"]["covers"]))
        if wrong:
            failed_cases.append({
                "model_client": client["name"],
                "case_id": case["id"],
                "failures": [
                    {"field": name, **answers} for name, answers in wrong.items()
                ],
            })
            # What the dashboard shows when somebody clicks the failing case.
            mismatches[case["id"]] = [
                {
                    "subject": name,
                    "field": "covers",
                    "expected": answers["expected"],
                    "actual": answers["actual"],
                }
                for name, answers in wrong.items()
            ]
    return client, failed_cases, elapsed_seconds, found, mismatches


def _write_report(model_client, failed_cases, elapsed_seconds, found, case_ids, mismatches):
    llm_costs = cost_utils.get_cost_tracker(_eval_run_id(model_client["name"]))
    cost_summary = {
        "model": llm_costs[0].model if llm_costs else None,
        "elapsed_seconds": elapsed_seconds,
        "total_input_tokens": sum(c.input_tokens for c in llm_costs),
        "total_output_tokens": sum(c.output_tokens for c in llm_costs),
        "total_cost_usd": float(cost_utils.sum_cost(llm_costs)),
    }
    accuracy = as_report({"covers": tally(found)})
    os.makedirs(EVALS_DIR, exist_ok=True)
    # Placeholders rather than empty strings: every line of this prompt is interpolated per
    # case, and archiving it built from blanks stores text no real call ever sends.
    run = record_run(
        EVALS_DIR,
        page_covers_organization_prompt(
            "<body, per case>", ["<its posts, per case>"], "<jurisdiction, per case>"
        ),
    )
    record_history(
        EVALS_DIR,
        model_client["name"],
        run,
        {field: counts["f1"] for field, counts in accuracy.items()},
        cost_summary,
        {cid: 0.0 if cid in {f["case_id"] for f in failed_cases} else 1.0 for cid in case_ids},
        accuracy=accuracy,
        mismatches=mismatches,
    )
    report_path = os.path.join(EVALS_DIR, f"{model_client['name']}-eval-report.yml")
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "run": run,
                "cost_summary": cost_summary,
                "accuracy": accuracy,
                "failed_cases": failed_cases,
            },
            f,
            sort_keys=False,
        )
    print(f"Saved evaluation report to {report_path}")
    return cost_summary


@pytest.mark.asyncio
async def test_provider_comparison(load_eval_cases):
    """Every provider, every case, one report each."""
    clients = [
        make_provider_client(p, page_covers_organization_prompt) for p in PROVIDER_COMPARISON
    ]
    results = await asyncio.gather(
        *[_run_provider(c, load_eval_cases) for c in clients], return_exceptions=True
    )

    comparison = {}
    failures = {}
    all_failed: list[dict] = []
    for provider_client, result in zip(clients, results):
        if isinstance(result, Exception):
            failures[provider_client["name"]] = repr(result)
            record_provider_failure(EVALS_DIR, provider_client["name"], repr(result))
            print(f"PROVIDER FAILED: {provider_client['name']}: {result!r}", flush=True)
            continue
        client, failed_cases, elapsed_seconds, found, mismatches = result
        cost_summary = _write_report(
            client,
            failed_cases,
            elapsed_seconds,
            found,
            [c["id"] for c in load_eval_cases],
            mismatches,
        )
        all_failed.extend(failed_cases)
        comparison[client["name"]] = {
            "elapsed_seconds": elapsed_seconds,
            "cost_usd": cost_summary["total_cost_usd"],
            "failed_cases": len(failed_cases),
            "passed_cases": len(load_eval_cases) - len(failed_cases),
        }

    write_comparison_report(EVALS_DIR, comparison, failures)

    assert not failures, f"Providers failed: {failures}"
    assert not all_failed, "Cases failed:\n  " + "\n  ".join(
        f'{c["model_client"]} {c["case_id"]}: '
        + ", ".join(
            f'{f["field"]} expected {f["expected"]}, got {f["actual"]}' for f in c["failures"]
        )
        for c in all_failed
    )
