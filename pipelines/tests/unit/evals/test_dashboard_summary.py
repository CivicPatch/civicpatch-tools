
import pytest
from dashboard_summary import eval_trends, gate_failure, gate_floor, issues, provider_verdicts
from eval_records import CaseTally, EvalResults, HistoryRun, MetricResult, Mismatch

pytestmark = pytest.mark.unit


def _metric(provider, metric, f1, missing=0, correct=10, ran_at="2026-09-16T10:00:00+00:00"):
    return MetricResult(eval_name="officials", provider=provider, metric=metric, f1=f1, correct=correct,
                        missing=missing, cost_usd=0.01, ran_at=ran_at)


def _tally(provider, failed_ids, passed, total, ran_at="2026-09-16T10:00:00+00:00"):
    return CaseTally(eval_name="relevant_page", provider=provider, passed=passed, total=total,
                     failed_case_ids=failed_ids, cost_usd=0.02, ran_at=ran_at)


def _results(metrics=(), case_tallies=()):
    return EvalResults(metrics=list(metrics), case_tallies=list(case_tallies))


def _history_run(timestamp, scores, provider="open_router-Atlas"):
    return HistoryRun(timestamp=timestamp, provider=provider, prompt_sha256="a", scores=scores)


def test_a_provider_below_a_gate_floor_is_blocked_on_that_metric():
    [verdict] = provider_verdicts(_results([_metric("Atlas", "primary_role", 0.5), _metric("Atlas", "district", 1.0)]), {})
    assert verdict.blocked
    assert [failure.metric for failure in verdict.gate_failures] == ["primary_role"]
    assert verdict.priority_scores == {"primary_role": 0.5, "district": 1.0}


def test_a_provider_failing_cases_is_blocked_with_the_case_ids():
    [verdict] = provider_verdicts(_results(case_tallies=[_tally("Atlas", ["milton"], 2, 3)]), {})
    assert verdict.blocked
    assert verdict.failed_case_ids == ["milton"]
    assert (verdict.cases_passed, verdict.cases_total) == (2, 3)


def test_a_verdict_reports_when_the_provider_last_ran():
    [verdict] = provider_verdicts(_results(
        [_metric("Atlas", "primary_role", 1.0, ran_at="2026-09-16T19:43:41+00:00")],
        [_tally("Atlas", [], 3, 3, ran_at="2026-09-15T08:00:00+00:00")],
    ), {})
    assert verdict.ran_at == "2026-09-16T19:43:41+00:00"


def test_a_gate_failure_names_the_cases_with_the_most_wrong_values_first():
    def wrong(field):
        return Mismatch(person="Ann", field=field, expected="Council Member", actual=None)

    failure = gate_failure("primary_role", {
        "coleman_council": [wrong("primary_role"), wrong("phone")],
        "la_porte_council": [wrong("primary_role"), wrong("primary_role")],
        "austin_council": [wrong("email")],
    })
    assert [(c.case_id, c.count) for c in failure.cases] == [("la_porte_council", 2), ("coleman_council", 1)]


def test_a_metric_is_charted_only_once_a_provider_has_two_points():
    trends = eval_trends([_history_run("1", {"url": 0.9, "email": 1.0}), _history_run("2", {"url": 0.8})])
    assert [chart.metric for chart in trends.charts] == ["url"]
    assert [p.score for p in trends.charts[0].series[0].points] == [0.9, 0.8]


def test_a_zero_threshold_is_no_gate_at_all():
    assert gate_floor("email") is None
    assert gate_floor("primary_role") == 0.96


def test_issues_put_gate_failures_before_noise():
    history = [_history_run("1", {"email": 0.2}), _history_run("2", {"email": 1.0})]
    found = issues(
        {"officials": _results([_metric("Atlas", "email", 0.95), _metric("Atlas", "primary_role", 0.5)])},
        {"officials": history},
    )
    assert [(i.kind, i.metric) for i in found] == [("gate_failed", "primary_role"), ("wide_swing", "email")]


def test_many_missing_values_is_an_issue_even_above_the_gate():
    [issue] = issues({"officials": _results([_metric("Atlas", "phone", 0.99, missing=12, correct=40)])}, {})
    assert issue.kind == "many_missing"
    assert (issue.missing_count, issue.expected_count) == (12, 52)


def test_failed_cases_are_an_issue():
    [issue] = issues({"relevant_page": _results(case_tallies=[_tally("Atlas", ["milton"], 2, 3)])}, {})
    assert issue.kind == "cases_failed"
    assert issue.failed_case_ids == ["milton"]
