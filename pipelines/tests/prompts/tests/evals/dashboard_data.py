import json
import pathlib

import yaml
from eval_records import (
    CaseMismatches,
    CasePrompts,
    CaseTally,
    EvalResults,
    HistoryRun,
    MetricResult,
    Mismatch,
    short_provider,
)

EVALS = pathlib.Path("tests/prompts/tests/evals")
# The one eval not found by its report: F1 per field from comparison.yml, named apart from its folder.
OFFICIALS = "officials"
OFFICIALS_DIR = "municipal_officials"
# Relative to dashboard/, since the page links to them; a dataset folder shares its eval's name.
DATASETS = "../../../datasets/local"
REPORT_SUFFIX = "-eval-report.yml"
PASS_FAIL_KEY = "failed_cases"


def eval_dirs() -> dict[str, pathlib.Path]:
    """Every eval the dashboard shows: officials, then each folder whose report is pass/fail
    (`write_pass_fail_report`'s shape), so a new eval shows up without being listed here."""
    found = {
        directory.name: directory
        for directory in sorted(EVALS.iterdir())
        if directory.is_dir() and directory.name != OFFICIALS_DIR and _is_pass_fail(directory)
    }
    return {OFFICIALS: EVALS / OFFICIALS_DIR, **found}


def dataset_dir(eval_name: str) -> str:
    return f"{DATASETS}/{OFFICIALS_DIR if eval_name == OFFICIALS else eval_name}"


def _is_pass_fail(directory: pathlib.Path) -> bool:
    return any(PASS_FAIL_KEY in report for _, report in _reports(directory))


def _load_yaml(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_history(directory: pathlib.Path) -> list[HistoryRun]:
    return [HistoryRun(**run) for run in _load_yaml(directory / "history.yml").get("runs") or []]


def _read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_prompt_texts(directory: pathlib.Path, runs: list[HistoryRun]) -> dict[str, str]:
    shas = {run.prompt_sha256 for run in runs if run.prompt_sha256}
    return {sha: _read_text(directory / "_prompts" / f"{sha}.txt") for sha in shas}


def _parse_mismatches(raw: dict) -> CaseMismatches:
    return {case_id: [Mismatch(**row) for row in rows] for case_id, rows in raw.items()}


def _report_provider(path: pathlib.Path) -> str:
    return path.name.removesuffix(REPORT_SUFFIX)


def _reports(directory: pathlib.Path) -> list[tuple[pathlib.Path, dict]]:
    return [(path, _load_yaml(path)) for path in sorted(directory.glob(f"*{REPORT_SUFFIX}"))]


def read_latest_mismatches(directory: pathlib.Path) -> dict[str, CaseMismatches]:
    """Latest run only: each report is overwritten per run."""
    return {
        short_provider(_report_provider(path)): _parse_mismatches(report["mismatches"])
        for path, report in _reports(directory)
        if report.get("mismatches")
    }


def read_latest_case_prompts(directory: pathlib.Path) -> dict[str, CasePrompts]:
    """Latest run only, like `read_latest_mismatches`."""
    return {
        short_provider(_report_provider(path)): CasePrompts(
            template_sha256=(report.get("run") or {}).get("prompt_sha256"),
            prompts=report["case_prompts"],
        )
        for path, report in _reports(directory)
        if report.get("case_prompts")
    }


def prompts_dir(directory: pathlib.Path) -> str:
    """Relative to dashboard/, since the page fetches from it."""
    return f"../{directory.name}/_prompts"


def read_run_mismatches(directory: pathlib.Path, runs: list[HistoryRun]) -> dict[str, CaseMismatches]:
    """Keyed by HistoryRun.mismatches_file."""
    return {
        run.mismatches_file: _parse_mismatches(_load_yaml(directory / run.mismatches_file).get("mismatches") or {})
        for run in runs
        if run.mismatches_file
    }


def _ran_at(report: dict) -> str | None:
    return (report.get("run") or {}).get("timestamp")


def _metric_results(eval_name: str, provider: str, report: dict, cost_usd: float | None) -> list[MetricResult]:
    return [
        MetricResult(eval_name=eval_name, provider=provider, metric=field, f1=counts.get("f1"),
                     correct=counts.get("correct"), missing=counts.get("missing"), cost_usd=cost_usd,
                     ran_at=_ran_at(report))
        for field, counts in (report.get("accuracy") or {}).items()
    ]


def read_officials_results() -> EvalResults:
    directory = EVALS / OFFICIALS_DIR
    comparison = _load_yaml(directory / "comparison.yml").get("providers") or {}
    return EvalResults(metrics=[
        result
        for provider, summary in comparison.items()
        for result in _metric_results(
            "officials",
            short_provider(provider),
            _load_yaml(directory / f"{provider}{REPORT_SUFFIX}"),
            summary.get("cost_usd"),
        )
    ])


def _report_cost(report: dict) -> float | None:
    return (report.get("cost_summary") or {}).get("total_cost_usd")


_DASHBOARD_DIR = pathlib.Path(__file__).parent / "dashboard"
# Keys in a case's expected.yml that hold its answer or a note, not something the prompt was given.
_NOT_PROMPT_INPUTS = {"page", "covers", "people", "expected_url", "thought", "thoughts", "source", "generated"}


def _as_text(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def read_case_inputs(eval_name: str) -> dict[str, dict[str, str]]:
    """Each case's own prompt inputs, from its expected.yml: what fills the prompt's placeholders."""
    inputs = {}
    for expected_path in sorted((_DASHBOARD_DIR / dataset_dir(eval_name)).glob("*/expected.yml")):
        expected = _load_yaml(expected_path)
        inputs[expected_path.parent.name] = {
            key: _as_text(value) for key, value in expected.items() if key not in _NOT_PROMPT_INPUTS
        }
    return inputs


def _case_tally(eval_name: str, provider: str, report: dict, comparison: dict) -> CaseTally:
    failed_ids = [f.get("case_id") for f in report["failed_cases"]]
    # Single-provider evals write no comparison.yml, so fall back to the report's own count.
    passed = (comparison.get(provider) or {}).get("passed_cases", report.get("passed_cases"))
    total = report.get("total_cases")
    if total is None and passed is not None:
        total = passed + len(failed_ids)
    return CaseTally(eval_name=eval_name, provider=short_provider(provider), passed=passed or 0, total=total,
                     failed_case_ids=failed_ids,
                     cost_usd=_report_cost(report), ran_at=_ran_at(report))


def read_pass_fail_results(eval_name: str, directory: pathlib.Path) -> EvalResults:
    comparison = _load_yaml(directory / "comparison.yml").get("providers") or {}
    reports = [(_report_provider(path), report) for path, report in _reports(directory) if PASS_FAIL_KEY in report]
    return EvalResults(
        metrics=[
            result
            for provider, report in reports
            for result in _metric_results(eval_name, short_provider(provider), report, _report_cost(report))
        ],
        case_tallies=[_case_tally(eval_name, provider, report, comparison) for provider, report in reports],
    )


def read_results(dirs: dict[str, pathlib.Path]) -> dict[str, EvalResults]:
    return {
        name: read_officials_results() if name == OFFICIALS else read_pass_fail_results(name, directory)
        for name, directory in dirs.items()
    }
