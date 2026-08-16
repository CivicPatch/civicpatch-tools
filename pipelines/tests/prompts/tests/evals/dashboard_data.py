"""Reading eval reports off disk into one shape the dashboard can render.

The evals still disagree on report layout — officials emits disposition counts per field,
relevant_page and find_jurisdiction_url emit a failed-case list. Each gets a small adapter
here so the rendering never learns those differences, and converging the scorers later
changes this file only.

Reads only. Never runs an eval, never edits a fixture.
"""

import pathlib

import yaml

EVALS = pathlib.Path("tests/prompts/tests/evals")
EVAL_DIRS = {
    "officials": EVALS / "municipal_officials",
    "relevant_page": EVALS / "relevant_page",
    "find_jurisdiction_url": EVALS / "find_jurisdiction_url",
}
# Where each eval's case fixtures live, so a failing case can link to the page it was scored
# against. Relative from the dashboard, which sits at tests/prompts/tests/evals/.
DATASET_DIRS = {
    "officials": "../../datasets/local/municipal_officials",
    "relevant_page": "../../datasets/local/relevant_page",
    "find_jurisdiction_url": "../../datasets/local/find_jurisdiction_url",
}

# Metrics the posts/memberships model is built on. Everything else is supporting detail.
PRIORITY = ("primary_role", "district")
# A swing this wide across runs of the same prompt means the number is not a quality signal.
WIDE_SWING = 0.15


def load(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_history(directory: pathlib.Path) -> list[dict]:
    return load(directory / "history.yml").get("runs") or []


def prompt_text(directory: pathlib.Path, sha: str) -> str:
    path = directory / "_prompts" / f"{sha}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def prompt_versions(directory: pathlib.Path) -> dict[str, dict]:
    """Each prompt version with the runs that used it, newest first."""
    versions: dict[str, dict] = {}
    for run in sorted(read_history(directory), key=lambda r: r.get("timestamp") or "", reverse=True):
        sha = run.get("prompt_sha256")
        if not sha:
            continue
        entry = versions.setdefault(sha, {"sha": sha, "runs": [], "text": prompt_text(directory, sha)})
        entry["runs"].append(run)
    return versions


def swing(directory: pathlib.Path, provider: str, metric: str) -> float:
    values = [
        r["scores"][metric]
        for r in read_history(directory)
        if r.get("provider") == provider and metric in (r.get("scores") or {})
    ]
    return (max(values) - min(values)) if len(values) > 1 else 0.0


def case_stability(runs: list[dict]) -> tuple[dict, dict]:
    """How often each case changed between consecutive runs of the same provider.

    Pooled across providers deliberately: a case that flaps is a property of the case — the
    page, the fixture, how much the answer depends on sampling — not of who ran it.
    """
    changed: dict[str, int] = {}
    compared: dict[str, int] = {}
    by_provider: dict[str, list[dict]] = {}
    for run in runs:
        by_provider.setdefault(run.get("provider") or "?", []).append(run)
    for provider_runs in by_provider.values():
        ordered = sorted(provider_runs, key=lambda r: r.get("timestamp") or "")
        for older, newer in zip(ordered, ordered[1:]):
            before, after = older.get("cases") or {}, newer.get("cases") or {}
            for case, value in after.items():
                if case not in before:
                    continue
                compared[case] = compared.get(case, 0) + 1
                if abs(value - before[case]) > 1e-9:
                    changed[case] = changed.get(case, 0) + 1
    return changed, compared


def read_officials() -> list[dict]:
    rows = []
    directory = EVAL_DIRS["officials"]
    comparison = load(directory / "comparison.yml").get("providers") or {}
    for provider, summary in comparison.items():
        report = load(directory / f"{provider}-eval-report.yml")
        accuracy = report.get("accuracy") or {}
        if not accuracy:
            continue
        for field, counts in accuracy.items():
            rows.append(
                {
                    "eval": "officials",
                    "provider": provider.replace("open_router-", ""),
                    "metric": field,
                    "f1": counts.get("f1"),
                    "correct": counts.get("correct"),
                    "missing": counts.get("missing"),
                    "spurious": counts.get("spurious"),
                    "wrong": counts.get("wrong"),
                    "cost": summary.get("cost_usd"),
                    "seconds": summary.get("elapsed_seconds"),
                    "run": report.get("run") or {},
                }
            )
    return rows


def read_mismatches(directory: pathlib.Path) -> dict[str, dict]:
    """Per-person expected/actual, by provider then case.

    Latest run only — each report is overwritten in place, so history holds the aggregate
    while this holds the detail behind the newest one.
    """
    out: dict[str, dict] = {}
    for report_path in sorted(directory.glob("*-eval-report.yml")):
        provider = report_path.name.removesuffix("-eval-report.yml").replace("open_router-", "")
        rows = load(report_path).get("mismatches") or {}
        if rows:
            out[provider] = rows
    return out


def read_pass_fail(name: str) -> list[dict]:
    """relevant_page and find_jurisdiction_url: a failed-case list, plus accuracy if present."""
    rows = []
    directory = EVAL_DIRS[name]
    comparison = load(directory / "comparison.yml").get("providers") or {}
    for path in sorted(directory.glob("*-eval-report.yml")):
        provider = path.name.removesuffix("-eval-report.yml")
        report = load(path)
        if "failed_cases" not in report:
            continue
        cost = (report.get("cost_summary") or {}).get("total_cost_usd")
        seconds = (report.get("cost_summary") or {}).get("elapsed_seconds")
        run = report.get("run") or {}
        short = provider.replace("open_router-", "")
        for field, counts in (report.get("accuracy") or {}).items():
            rows.append(
                {
                    "eval": name, "provider": short, "metric": field,
                    "f1": counts.get("f1"), "correct": counts.get("correct"),
                    "missing": counts.get("missing"), "spurious": counts.get("spurious"),
                    "wrong": counts.get("wrong"), "cost": cost, "seconds": seconds, "run": run,
                }
            )
        failed = len(report["failed_cases"])
        # comparison.yml first, then the report's own count. Without the fallback a
        # single-provider eval — which writes no comparison.yml — renders a fully passing run
        # as "0 passed, 0 failed", indistinguishable from one that ran nothing.
        passed = (comparison.get(provider) or {}).get("passed_cases", report.get("passed_cases"))
        total = report.get("total_cases")
        if total is None and passed is not None:
            total = passed + failed
        rows.append(
            {
                "eval": name, "provider": short, "metric": "cases passed",
                "passed": passed if passed is not None else 0, "total": total, "failed": failed,
                "failed_ids": [f.get("case_id") for f in report["failed_cases"]],
                "cost": cost, "seconds": seconds, "run": run,
            }
        )
    return rows


def collect() -> list[dict]:
    return read_officials() + read_pass_fail("relevant_page") + read_pass_fail("find_jurisdiction_url")


def score(row: dict) -> float | None:
    """Every eval reduces to "what fraction went right", however it counts."""
    if row.get("f1") is not None:
        return row["f1"]
    return row["passed"] / row["total"] if row.get("total") else None
