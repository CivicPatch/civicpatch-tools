import asyncio
import os
import pathlib
import time
from typing import cast

import pytest
import pytest_asyncio
import yaml
from eval_utils import (
    PROVIDER_COMPARISON,
    make_provider_client,
    record_history,
    record_run,
    write_comparison_report,
)
from runners.people_collector.schemas import (
    PeopleArrayLLMResponseSchema,
    ExtractedPersonRecord,
)
from services.open_router.llm import run_prompt as run_together_prompt
from services.open_router.prompts import municipality_officials_prompt
from utils import cost_utils
from scoring import EVAL_TAXONOMY, aggregate, failing_people, score_cases
from accuracy import (
    GATE_THRESHOLDS as ACCURACY_THRESHOLDS,
    as_report,
    case_dispositions,
    case_mismatches,
    merge_dispositions,
    summarize,
)

pytestmark = pytest.mark.evals

# Report-only, and deliberately strict: every person whose role or seat was not fully
# recovered gets a printed line. The run passes or fails on the aggregate gates in
# accuracy.py — this is what makes a failing one diagnosable without re-running.
PER_PERSON_THRESHOLDS = {"roles": 1.0, "designations": 1.0}

# The prompt asks for *currently serving* officials, so its answer depends on the date it
# is run. Pinned here, because otherwise the fixtures rot: 9 of 62 expected people have
# terms that have now ended (board_of_aldermen 3/5, mixed_current_past 3/6,
# redundant_place_role 3/6), and a model correctly applying today's date would be marked
# wrong for excluding them. Must sit in [latest expected start_date, earliest expected
# end_date) = ["2025-05", "2026").
EVAL_CURRENT_DATE = "2025-09-01"


def make_together_prompt(known_roles):
    return municipality_officials_prompt(known_roles, current_date=EVAL_CURRENT_DATE)




def _progress(name: str, message: str) -> None:
    """Cases run concurrently under asyncio.gather, so a bare print says nothing about how
    far along the run is. Every line carries the provider, a done/total count and elapsed
    seconds, and flushes — pytest buffers otherwise and you see the lot at the end."""
    done, total = _PROGRESS[name]
    elapsed = time.time() - _RUN_STARTED_AT
    print(f"[{elapsed:6.1f}s] {name:26} {done:>2}/{total:<2} {message}", flush=True)


_PROGRESS: dict = {}
_RUN_STARTED_AT = time.time()


def _eval_run_id(provider_name: str) -> str:
    """One id per provider: costs key on the run, and every provider here shares an ocdid."""
    return f"run-eval-{provider_name}"


async def _run_single_case(model_client, case, ocdid):
    run_prompt = model_client["run_prompt"]
    make_prompt = model_client["make_prompt"]
    extra_kwargs = model_client.get("extra_kwargs", {})
    name = model_client["name"]

    _progress(name, f"START  {case['id']}")
    started = time.time()

    known_roles = case["expected"].get("known_roles", [])
    prompt = make_prompt(known_roles)
    try:
        response = await run_prompt(
            _eval_run_id(name),
            ocdid,
            prompt,
            prompt_name="municipality_officials",
            response_schema=PeopleArrayLLMResponseSchema,
            content=case["input"],
            **extra_kwargs,
        )
    except Exception as exc:
        # Surface which case died and why. gather() would otherwise report one exception
        # for the whole batch with no indication of which provider or case produced it.
        _PROGRESS[name][0] += 1
        _progress(name, f"FAILED {case['id']} after {time.time() - started:.1f}s: {exc!r}")
        raise

    _PROGRESS[name][0] += 1
    _progress(name, f"done   {case['id']} in {time.time() - started:.1f}s")
    expected = [ExtractedPersonRecord(**person) for person in case["expected"]["people"]]
    actual = cast(PeopleArrayLLMResponseSchema, response)
    case_path = case.get("case_path", "unknown_case")
    with open(
        f"{case_path}/{model_client['name']}-actual.yml", "w", encoding="utf-8"
    ) as f:
        yaml_output = yaml.safe_dump(
            PeopleArrayLLMResponseSchema.model_dump(actual), sort_keys=False
        )
        f.write(yaml_output)

    case_scores = score_cases(actual.people, expected)
    case_aggregate = {}
    if not expected and actual.people:
        case_aggregate["hallucination"] = 0.0
    else:
        # Same present-keys rule as aggregate(). This used to default a missing key to 0.0
        # and divide by everyone, so the per-case breakdown in each report diluted the
        # recall-only dimensions while the overall report did not — the two numbers
        # disagreed for the same run.
        all_keys = set()
        for score in case_scores:
            all_keys.update(score["scores"].keys())
        for key in all_keys:
            present = [s["scores"][key] for s in case_scores if key in s["scores"]]
            if present:
                case_aggregate[key] = sum(present) / len(present)

    dispositions = case_dispositions(actual.people, expected, EVAL_TAXONOMY)
    mismatches = case_mismatches(actual.people, expected, EVAL_TAXONOMY)
    return case["id"], case_aggregate, case_scores, dispositions, mismatches


@pytest.mark.asyncio
async def run_eval(
    model_client,
    cases,
    ocdid="ocd-jurisdiction/country:us/state:tx/place:example/government",
):
    name = model_client["name"]
    _PROGRESS[name] = [0, len(cases)]
    batch_started = time.time()
    cost_utils.reset_cost_tracker(_eval_run_id(name))
    _progress(name, f"dispatching {len(cases)} cases concurrently")

    results = await asyncio.gather(
        *[_run_single_case(model_client, case, ocdid) for case in cases]
    )

    _progress(name, f"ALL DONE in {time.time() - batch_started:.1f}s")
    per_case_scores = [(case_id, agg) for case_id, agg, _, _, _ in results]
    scores = [case_scores for _, _, case_scores, _, _ in results]
    # Dispositions are counted across every person in the run, not averaged per case —
    # precision has no meaning inside one case that produced nothing.
    accuracy = summarize(merge_dispositions([d for _, _, _, d, _ in results]))
    # The per-person scores are returned, not discarded. Rebuilding them from the saved
    # -actual.yml was a second scoring implementation that silently drifted from this one.
    case_scores_by_id = {case_id: case_scores for case_id, _, case_scores, _, _ in results}
    # Per-person expected/actual, so the dashboard can show *what* differed rather than only
    # that something did. Keyed by case; empty entries dropped to keep the report readable.
    mismatches = {case_id: rows for case_id, _, _, _, rows in results if rows}
    return aggregate(scores), per_case_scores, accuracy, case_scores_by_id, mismatches


@pytest_asyncio.fixture
def load_eval_cases(base_dir="tests/prompts/datasets/local/municipal_officials"):
    base = pathlib.Path(base_dir)
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
            raise ValueError(f"Missing input.txt or expected.yml in {case_dir}")

        with open(expected_path, "r", encoding="utf-8") as f:
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
    """Every case comes from PROVIDER_COMPARISON, so the param is always
    `open_router:<provider>`.

    Two other branches used to live here. A "gemini" one referenced `run_gemini_prompt` and
    `make_gemini_prompt`, neither of which this module imports — it would have raised
    NameError had anything reached it. A bare "open_router" one sent no provider_order,
    which with allow_fallbacks=False is not a comparison of anything.
    """
    if not request.param.startswith("open_router:"):
        raise ValueError(f"Unknown model client: {request.param}")
    provider = request.param.split(":", 1)[1]
    return {
        "name": f"open_router-{provider}",
        "run_prompt": run_together_prompt,
        "make_prompt": make_together_prompt,
        "extra_kwargs": {
            "model_type": "STANDARD",
            "provider_order": [provider],
        },
    }


def _active_providers():
    only = os.environ.get("EVAL_PROVIDER")
    return [p for p in PROVIDER_COMPARISON if not only or p.split(":", 1)[1] == only]


async def _run_provider(client, cases):
    # The provider goes in the place slug, not a segment of its own. Costs key on the
    # ocdid and the three providers run concurrently, so they do need distinct ones — but
    # `.../place:example/{provider}/government` is not a valid ocdid: id_utils requires
    # every middle segment to be `label:value`. It parsed until a209e141e added state and
    # county parsing, and has raised on the first case of every provider ever since.
    ocdid = f"ocd-jurisdiction/country:us/state:tx/place:example_{client['name']}/government"
    start_time = time.time()
    report, per_case_scores, accuracy, case_scores_by_id, mismatches = await run_eval(
        client, cases, ocdid
    )
    elapsed_seconds = round(time.time() - start_time, 2)
    llm_costs = cost_utils.get_cost_tracker(_eval_run_id(client["name"]))["llm_costs"]
    return {
        "client": client,
        "report": report,
        "accuracy": accuracy,
        "per_case_scores": per_case_scores,
        "case_scores_by_id": case_scores_by_id,
        "mismatches": mismatches,
        "elapsed_seconds": elapsed_seconds,
        "llm_costs": llm_costs,
    }


@pytest.mark.asyncio
async def test_provider_comparison(load_eval_cases):
    """Runs all providers concurrently and writes one report per provider."""
    clients = [
        make_provider_client(p, make_together_prompt) for p in PROVIDER_COMPARISON
    ]
    results = await asyncio.gather(
        *[_run_provider(c, load_eval_cases) for c in clients], return_exceptions=True
    )

    evals_dir = "tests/prompts/tests/evals/municipal_officials"
    os.makedirs(evals_dir, exist_ok=True)

    comparison = {}
    failures = {}
    under_threshold: list[str] = []
    case_failures: dict[str, list] = {}
    for client, result in zip(clients, results):
        if isinstance(result, Exception):
            # Record it, don't just print. An all-failed run used to leave
            # `providers: {}` in comparison.yml with no indication that anything had gone
            # wrong — it read as "no data" rather than "everything blew up".
            failures[client["name"]] = repr(result)
            print(f"PROVIDER FAILED: {client['name']}: {result!r}", flush=True)
            continue
        llm_costs = result["llm_costs"]
        cost_summary = {
            "model": llm_costs[0]["model"] if llm_costs else None,
            # Read back from the response, not assumed from what was asked for — this is a
            # per-provider comparison, so which provider served is the premise of every
            # number below it. A set rather than [0]: routing is pinned, and this is what
            # would show it if that ever stopped being true.
            "providers": sorted({c["provider"] for c in llm_costs if c.get("provider")}),
            "elapsed_seconds": result["elapsed_seconds"],
            "total_input_tokens": sum(c["input_tokens"] for c in llm_costs),
            "total_output_tokens": sum(c["output_tokens"] for c in llm_costs),
            "total_cost_usd": float(sum(c["total_cost"] for c in llm_costs)),
        }
        accuracy_report = as_report(result["accuracy"])
        # A placeholder, not an empty list: `known_roles` is injected per case, and passing
        # [] omitted the line entirely — so the archived text was missing a block that two of
        # the fifteen cases actually send. Archive the template as structured, marking what
        # varies, rather than one case's rendering of it.
        run = record_run(evals_dir, make_together_prompt(["<injected per case>"]))
        record_history(
            evals_dir,
            client["name"],
            run,
            {field: counts["f1"] for field, counts in accuracy_report.items()},
            cost_summary,
            {
                # An empty aggregate means the case expected nobody and the model returned
                # nobody — the hallucination cases. That is a perfect result, not a zero.
                # Scoring it 0.0 made austin_city_manager_staff and nav_links_no_names look
                # like total failures for every provider in every case-level view.
                case_id: (sum(agg.values()) / len(agg)) if agg else 1.0
                for case_id, agg in result["per_case_scores"]
            },
        )
        report_path = os.path.join(evals_dir, f"{client['name']}-eval-report.yml")
        with open(report_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "run": run,
                    "cost_summary": cost_summary,
                    "accuracy": accuracy_report,
                    "aggregated_report": result["report"],
                    "per_case_scores": [
                        {"case_id": case_id, "scores": case_aggregate}
                        for case_id, case_aggregate in result["per_case_scores"]
                    ],
                    "mismatches": result["mismatches"],
                },
                f,
                sort_keys=False,
            )
        print(f"Saved provider comparison report to {report_path}")
        below = [
            f"{client['name']} {field}: F1={result['accuracy'][field].f1:.3f} < {floor:.2f}"
            for field, floor in ACCURACY_THRESHOLDS.items()
            if result["accuracy"][field].f1 is not None
            and result["accuracy"][field].f1 < floor
        ]
        under_threshold.extend(below)
        case_failures[client["name"]] = failing_people(
            result["case_scores_by_id"], PER_PERSON_THRESHOLDS
        )
        comparison[client["name"]] = {
            "elapsed_seconds": result["elapsed_seconds"],
            "cost_usd": cost_summary["total_cost_usd"],
            # F1 on the two dimensions the product depends on, first — the overall figure
            # is dominated by contact fields and ranks providers differently.
            "f1_primary_role": result["accuracy"]["primary_role"].f1,
            "f1_district": result["accuracy"]["district"].f1,
            **result["report"],
        }

    write_comparison_report(evals_dir, comparison, failures)

    # Without this the test passes when every provider dies — which is exactly what it did
    # while the ocdid above was invalid: 45 cases raised, nothing ran, green in 0.18s.
    assert not failures, f"Providers failed: {failures}"

    # Per-person detail is reported, not asserted: a single person below a floor is normal
    # and the aggregate gates are what decide fitness. Printing it is what makes a failing
    # aggregate diagnosable without re-running.
    for name, rows in case_failures.items():
        if rows:
            print(f"\n[{name}] {len(rows)} field(s) below a per-person floor:")
            for row in rows[:20]:
                print(
                    f"    {row['case_id']}/{row['person']} {row['field']}="
                    f"{row['score']:.2f} expected={row['expected']!r} actual={row['actual']!r}"
                )
    assert not under_threshold, "Accuracy below threshold:\n  " + "\n  ".join(under_threshold)
