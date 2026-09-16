"""Writes dashboard/dashboard-data.json for dashboard/index.html to render."""

import argparse
import pathlib

from dashboard_data import (
    DATASET_DIRS,
    EVAL_DIRS,
    read_history,
    read_latest_mismatches,
    read_prompt_texts,
    read_results,
    read_run_mismatches,
)
from dashboard_detail import build_prompt_versions, eval_detail
from dashboard_models import model_comparison, model_prompt_matrix
from dashboard_schema import DashboardPayload, EvalSection
from dashboard_summary import eval_trends, issues, provider_verdicts
from eval_records import EvalResults, HistoryRun

OUTPUT = pathlib.Path("tests/prompts/tests/evals/dashboard/dashboard-data.json")


def _eval_section(name: str, directory: pathlib.Path, results: EvalResults, runs: list[HistoryRun]) -> EvalSection:
    matrix = model_prompt_matrix(runs)
    latest_mismatches = read_latest_mismatches(directory)
    return EvalSection(
        eval_name=name,
        dataset_dir=DATASET_DIRS[name],
        verdicts=provider_verdicts(results, latest_mismatches),
        matrix=matrix,
        comparison=model_comparison(runs, matrix, read_run_mismatches(directory, runs)),
        trends=eval_trends(runs),
        prompt_versions=build_prompt_versions(runs, read_prompt_texts(directory, runs)),
        detail=eval_detail(results, runs),
        latest_mismatches=latest_mismatches,
    )


def write_dashboard(output: pathlib.Path = OUTPUT) -> int:
    """Split from main() so the evals' conftest can refresh the dashboard after every run."""
    results = read_results()
    result_count = sum(len(r.metrics) + len(r.case_tallies) for r in results.values())
    if not result_count:
        return 0
    histories = {name: read_history(directory) for name, directory in EVAL_DIRS.items()}
    payload = DashboardPayload(
        evals=[_eval_section(name, EVAL_DIRS[name], results[name], histories[name]) for name in EVAL_DIRS],
        issues=issues(results, histories),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload.model_dump_json(indent=1), encoding="utf-8")
    return result_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    count = write_dashboard(args.output)
    if not count:
        print("No eval reports found. Run the evals first.")
        return
    print(f"Wrote {args.output.resolve()} from {count} result(s)")


if __name__ == "__main__":
    main()
