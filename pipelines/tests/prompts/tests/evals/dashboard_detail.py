import difflib

from aggregation import SAME_SCORE, group_by
from dashboard_schema import (
    CaseMovement,
    CaseRow,
    CaseStability,
    DiffLine,
    DiffLineKind,
    EvalDetail,
    MetricCell,
    MetricRow,
    PromptVersion,
    RunSummary,
)
from dashboard_summary import WIDE_SWING, metric_swing, ordered_metrics
from eval_records import EvalResults, HistoryRun

CASES_PASSED = "cases passed"
DIFF_HEADERS = ("@@", "---", "+++")


def _diff_kind(line: str) -> DiffLineKind:
    if line.startswith("+"):
        return "added"
    if line.startswith("-"):
        return "removed"
    return "context"


def prompt_diff(old_text: str, new_text: str) -> list[DiffLine]:
    if not old_text or not new_text:
        return []
    lines = difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm="", n=1)
    # ---/+++ headers start like real changes and would be counted as them.
    return [DiffLine(kind=_diff_kind(line), text=line) for line in lines if not line.startswith(DIFF_HEADERS)]


def _oldest_first(runs: list[HistoryRun]) -> list[HistoryRun]:
    return sorted(runs, key=lambda r: r.timestamp)


def _newest_first(runs: list[HistoryRun]) -> list[HistoryRun]:
    return sorted(runs, key=lambda r: r.timestamp, reverse=True)


def _prompt_version(sha: str, prompt_runs: list[HistoryRun], previous: str | None, texts: dict[str, str]) -> PromptVersion:
    return PromptVersion(
        prompt_sha256=sha,
        text=texts.get(sha, ""),
        first_run_at=prompt_runs[-1].timestamp,
        last_run_at=prompt_runs[0].timestamp,
        providers=sorted({r.short_provider for r in prompt_runs}),
        runs=[RunSummary(timestamp=r.timestamp, provider=r.short_provider, scores=r.scores) for r in prompt_runs],
        previous_sha256=previous,
        diff=prompt_diff(texts.get(previous, ""), texts.get(sha, "")) if previous else [],
    )


def build_prompt_versions(runs: list[HistoryRun], texts: dict[str, str]) -> list[PromptVersion]:
    by_prompt = group_by(_newest_first([r for r in runs if r.prompt_sha256]), lambda r: r.prompt_sha256)
    shas = list(by_prompt)
    return [_prompt_version(sha, by_prompt[sha], previous, texts) for sha, previous in zip(shas, shas[1:] + [None])]


def _metric_cell(results: EvalResults, runs: list[HistoryRun], provider: str, metric: str) -> MetricCell | None:
    if metric == CASES_PASSED:
        tally = results.tally_for(provider)
        return MetricCell(score=tally.score, swing_is_wide=False, half_swing=0.0, missing_count=None) if tally else None
    result = results.metric_for(provider, metric)
    if result is None:
        return None
    swing = metric_swing(runs, provider, metric)
    return MetricCell(score=result.f1, swing_is_wide=swing > WIDE_SWING, half_swing=swing / 2, missing_count=result.missing)


def _metric_rows(results: EvalResults, runs: list[HistoryRun], providers: list[str]) -> list[MetricRow]:
    metrics = ordered_metrics({r.metric for r in results.metrics}) + ([CASES_PASSED] if results.case_tallies else [])
    return [
        MetricRow(metric=metric, cells=[_metric_cell(results, runs, provider, metric) for provider in providers])
        for metric in metrics
    ]


def _runs_by_provider(runs: list[HistoryRun]) -> dict[str, list[HistoryRun]]:
    return group_by(_oldest_first(runs), lambda r: r.short_provider)


def case_movement(provider: str, runs: list[HistoryRun]) -> CaseMovement | None:
    if len(runs) < 2:
        return None
    prior, latest = [run.cases for run in _oldest_first(runs)[-2:]]
    return CaseMovement(
        provider=provider,
        regressed=sorted(c for c, v in latest.items() if c in prior and v < prior[c] - SAME_SCORE),
        improved=sorted(c for c, v in latest.items() if c in prior and v > prior[c] + SAME_SCORE),
    )


def case_stability(runs: list[HistoryRun]) -> dict[str, CaseStability]:
    """Pooled across providers: a case that flaps is a property of the case, not of who ran it."""
    comparisons = [
        (case_id, abs(score - older.cases[case_id]) > SAME_SCORE)
        for provider_runs in _runs_by_provider(runs).values()
        for older, newer in zip(provider_runs, provider_runs[1:])
        for case_id, score in newer.cases.items()
        if case_id in older.cases
    ]
    return {
        case_id: "moves" if any(changed for _, changed in pairs) else "steady"
        for case_id, pairs in group_by(comparisons, lambda pair: pair[0]).items()
    }


def _case_rows(runs: list[HistoryRun]) -> tuple[list[str], list[CaseRow]]:
    latest = {provider: provider_runs[-1].cases for provider, provider_runs in _runs_by_provider(runs).items()}
    providers = sorted(latest)
    case_ids = {case_id for cases in latest.values() for case_id in cases}
    worst_first = sorted(case_ids, key=lambda c: (min(latest[p].get(c, 1.0) for p in providers), c))
    stability = case_stability(runs)
    rows = [
        CaseRow(case_id=case_id, scores=[latest[p].get(case_id) for p in providers], stability=stability.get(case_id, "unknown"))
        for case_id in worst_first
    ]
    return providers, rows


def eval_detail(results: EvalResults, runs: list[HistoryRun]) -> EvalDetail | None:
    if not results.providers:
        return None
    case_providers, case_rows = _case_rows(runs)
    movements = [case_movement(p, provider_runs) for p, provider_runs in sorted(_runs_by_provider(runs).items())]
    return EvalDetail(
        providers=results.providers,
        metric_rows=_metric_rows(results, runs, results.providers),
        case_providers=case_providers,
        case_rows=case_rows,
        movements=[m for m in movements if m is not None],
    )
