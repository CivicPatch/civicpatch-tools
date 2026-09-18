import pathlib

import yaml

from eval_records import CaseMismatches, CaseTally, EvalResults, HistoryRun, MetricResult, Mismatch, short_provider

EVALS = pathlib.Path("tests/prompts/tests/evals")
EVAL_DIRS = {
    "officials": EVALS / "municipal_officials",
    "relevant_page": EVALS / "relevant_page",
    "page_covers": EVALS / "page_covers",
    "find_jurisdiction_url": EVALS / "find_jurisdiction_url",
}
# Relative to dashboard/, since the page links to them.
DATASET_DIRS = {
    "officials": "../../../datasets/local/municipal_officials",
    "relevant_page": "../../../datasets/local/relevant_page",
    "page_covers": "../../../datasets/local/page_covers",
    "find_jurisdiction_url": "../../../datasets/local/find_jurisdiction_url",
}
REPORT_SUFFIX = "-eval-report.yml"


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
    directory = EVAL_DIRS["officials"]
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


def _case_tally(eval_name: str, provider: str, report: dict, comparison: dict) -> CaseTally:
    failed_ids = [f.get("case_id") for f in report["failed_cases"]]
    # Single-provider evals write no comparison.yml, so fall back to the report's own count.
    passed = (comparison.get(provider) or {}).get("passed_cases", report.get("passed_cases"))
    total = report.get("total_cases")
    if total is None and passed is not None:
        total = passed + len(failed_ids)
    return CaseTally(eval_name=eval_name, provider=short_provider(provider), passed=passed or 0, total=total,
                     failed_case_ids=failed_ids, cost_usd=_report_cost(report), ran_at=_ran_at(report))


def read_pass_fail_results(eval_name: str) -> EvalResults:
    directory = EVAL_DIRS[eval_name]
    comparison = _load_yaml(directory / "comparison.yml").get("providers") or {}
    reports = [(_report_provider(path), report) for path, report in _reports(directory) if "failed_cases" in report]
    return EvalResults(
        metrics=[
            result
            for provider, report in reports
            for result in _metric_results(eval_name, short_provider(provider), report, _report_cost(report))
        ],
        case_tallies=[_case_tally(eval_name, provider, report, comparison) for provider, report in reports],
    )


def read_results() -> dict[str, EvalResults]:
    return {
        "officials": read_officials_results(),
        "relevant_page": read_pass_fail_results("relevant_page"),
        "page_covers": read_pass_fail_results("page_covers"),
        "find_jurisdiction_url": read_pass_fail_results("find_jurisdiction_url"),
    }
