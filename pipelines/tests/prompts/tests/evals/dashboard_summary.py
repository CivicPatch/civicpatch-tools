from accuracy import GATE_THRESHOLDS
from dashboard_schema import (
    CaseCount,
    EvalTrends,
    GateFailure,
    Issue,
    ProviderVerdict,
    TrendChart,
    TrendPoint,
    TrendSeries,
)
from eval_records import CaseMismatches, CaseTally, EvalResults, HistoryRun, MetricResult

# What the posts/memberships model is built on.
PRIORITY = ("primary_role", "district")
METRIC_ORDER = list(PRIORITY) + [
    "person", "url", "designations_other", "email", "phone", "start_date", "end_date", "image",
]
# Wider than this across runs of one prompt, a metric is noise, not signal.
WIDE_SWING = 0.15
MANY_MISSING = 10
ISSUE_LIMIT = 12


def gate_floor(metric: str) -> float | None:
    """A 0.0 threshold means ungated, not a floor of zero."""
    return GATE_THRESHOLDS.get(metric) or None


def fails_gate(result: MetricResult) -> bool:
    floor = gate_floor(result.metric)
    return result.f1 is not None and floor is not None and result.f1 < floor


def ordered_metrics(metrics: set[str]) -> list[str]:
    return [m for m in METRIC_ORDER if m in metrics] + sorted(metrics - set(METRIC_ORDER))


def metric_swing(runs: list[HistoryRun], provider: str, metric: str) -> float:
    values = [r.scores[metric] for r in runs if r.short_provider == provider and metric in r.scores]
    return max(values) - min(values) if len(values) > 1 else 0.0


def gate_failure(metric: str, mismatches: CaseMismatches) -> GateFailure:
    """Cases with the most wrong values for the metric first."""
    counts = [(case_id, sum(1 for m in rows if m.field == metric)) for case_id, rows in mismatches.items()]
    ranked = sorted((pair for pair in counts if pair[1]), key=lambda pair: (-pair[1], pair[0]))
    return GateFailure(metric=metric, cases=[CaseCount(case_id=case_id, count=count) for case_id, count in ranked])


def _provider_verdict(provider: str, results: EvalResults, mismatches: CaseMismatches) -> ProviderVerdict:
    metrics = results.metrics_for(provider)
    tally = results.tally_for(provider)
    gate_failures = [gate_failure(r.metric, mismatches) for r in metrics if fails_gate(r)]
    failed_ids = tally.failed_case_ids if tally else []
    costs = [r.cost_usd for r in metrics if r.cost_usd is not None] + ([tally.cost_usd] if tally else [])
    run_times = [r.ran_at for r in metrics if r.ran_at] + ([tally.ran_at] if tally and tally.ran_at else [])
    return ProviderVerdict(
        provider=provider,
        blocked=bool(gate_failures or failed_ids),
        gate_failures=gate_failures,
        failed_case_ids=failed_ids,
        cases_passed=tally.passed if tally else None,
        cases_total=tally.total if tally else None,
        priority_scores={r.metric: r.f1 for r in metrics if r.metric in PRIORITY and r.f1 is not None},
        cost_usd=next((cost for cost in costs if cost is not None), None),
        ran_at=max(run_times, default=None),
    )


def provider_verdicts(results: EvalResults, latest_mismatches: dict[str, CaseMismatches]) -> list[ProviderVerdict]:
    return [_provider_verdict(provider, results, latest_mismatches.get(provider, {})) for provider in results.providers]


def _series(runs: list[HistoryRun], provider: str, metric: str) -> TrendSeries:
    points = [
        TrendPoint(timestamp=r.timestamp, prompt_sha256=r.prompt_sha256 or "unknown", score=r.scores[metric])
        for r in sorted(runs, key=lambda r: r.timestamp)
        if r.short_provider == provider and metric in r.scores
    ]
    return TrendSeries(provider=provider, points=points)


def eval_trends(runs: list[HistoryRun]) -> EvalTrends:
    providers = sorted({r.short_provider for r in runs})
    charts = []
    for metric in ordered_metrics({m for r in runs for m in r.scores}):
        series = [s for s in (_series(runs, p, metric) for p in providers) if len(s.points) > 1]
        if series:
            charts.append(TrendChart(metric=metric, is_priority=metric in PRIORITY,
                                     gate_floor=gate_floor(metric), series=series))
    return EvalTrends(providers=providers, charts=charts, run_count=len(runs))


def _metric_issue(result: MetricResult, runs: list[HistoryRun]) -> Issue | None:
    if result.f1 is None:
        return None
    base = {"eval_name": result.eval_name, "provider": result.provider, "metric": result.metric}
    if fails_gate(result):
        return Issue(kind="gate_failed", severity=0, **base, score=result.f1, gate_floor=gate_floor(result.metric))
    missing = result.missing or 0
    if missing >= MANY_MISSING:
        return Issue(kind="many_missing", severity=1, **base, missing_count=missing,
                     expected_count=(result.correct or 0) + missing)
    swing = metric_swing(runs, result.provider, result.metric)
    if swing > WIDE_SWING:
        return Issue(kind="wide_swing", severity=2, **base, swing=swing / 2)
    return None


def _tally_issue(tally: CaseTally) -> Issue | None:
    if not tally.failed_case_ids:
        return None
    return Issue(kind="cases_failed", severity=0, eval_name=tally.eval_name, provider=tally.provider,
                 failed_case_ids=tally.failed_case_ids)


def _eval_issues(eval_results: EvalResults, runs: list[HistoryRun]) -> list[Issue | None]:
    return [_metric_issue(r, runs) for r in eval_results.metrics] + [_tally_issue(t) for t in eval_results.case_tallies]


def issues(results: dict[str, EvalResults], histories: dict[str, list[HistoryRun]]) -> list[Issue]:
    found = [
        issue
        for eval_name, eval_results in results.items()
        for issue in _eval_issues(eval_results, histories.get(eval_name, []))
        if issue is not None
    ]
    return sorted(found, key=lambda issue: issue.severity)[:ISSUE_LIMIT]
