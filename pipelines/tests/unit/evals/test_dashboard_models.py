
import pytest
from dashboard_models import (
    case_changes,
    compare_lineages,
    default_pair,
    model_prompt_matrix,
)
from eval_records import HistoryRun, Mismatch

pytestmark = pytest.mark.unit


def _run(sha, model, provider, timestamp, cases, mismatches_file=None, cost_usd=None):
    return HistoryRun(prompt_sha256=sha, model=model, provider=provider, timestamp=timestamp, cases=cases,
                      mismatches_file=mismatches_file, cost_usd=cost_usd)


def _cells_by_lineage(matrix, sha):
    row = next(r for r in matrix.rows if r.prompt_sha256 == sha)
    return {(lineage.model, lineage.provider): cell for lineage, cell in zip(matrix.lineages, row.cells)}


def test_runs_of_the_same_prompt_and_lineage_average_into_one_cell():
    matrix = model_prompt_matrix([
        _run("aaa", "v4", "Atlas", "1", {"x": 1.0, "y": 0.0}),
        _run("aaa", "v4", "Atlas", "2", {"x": 1.0, "y": 1.0}),
    ])
    cell = _cells_by_lineage(matrix, "aaa")[("v4", "Atlas")]
    assert cell.mean_score == 0.75
    assert cell.run_count == 2


def test_a_cell_averages_the_cost_of_the_runs_that_stated_one():
    matrix = model_prompt_matrix([
        _run("aaa", "v4", "Atlas", "1", {"x": 1.0}, cost_usd=0.02),
        _run("aaa", "v4", "Atlas", "2", {"x": 1.0}, cost_usd=0.04),
        _run("aaa", "v4", "Atlas", "3", {"x": 1.0}),
    ])
    assert _cells_by_lineage(matrix, "aaa")[("v4", "Atlas")].mean_cost_usd == pytest.approx(0.03)


def test_a_pairing_that_never_ran_has_no_cell():
    matrix = model_prompt_matrix([
        _run("old", "v4", "Atlas", "1", {"x": 1.0}),
        _run("new", "v5", "Atlas", "2", {"x": 1.0}),
    ])
    assert _cells_by_lineage(matrix, "new")[("v4", "Atlas")] is None
    assert _cells_by_lineage(matrix, "old")[("v5", "Atlas")] is None


def test_prompts_are_ordered_by_their_newest_run():
    matrix = model_prompt_matrix([
        _run("first", "v4", "Atlas", "1", {"x": 1.0}),
        _run("second", "v4", "Atlas", "2", {"x": 1.0}),
        _run("first", "v5", "Atlas", "3", {"x": 1.0}),
    ])
    assert [row.prompt_sha256 for row in matrix.rows] == ["first", "second"]


def test_the_same_model_on_two_providers_is_two_columns():
    matrix = model_prompt_matrix([
        _run("aaa", "v4", "open_router-Atlas", "1", {"x": 1.0}),
        _run("aaa", "v4", "open_router-DigitalOcean", "1", {"x": 0.5}),
    ])
    assert [(lineage.model, lineage.provider) for lineage in matrix.lineages] == [("v4", "Atlas"), ("v4", "DigitalOcean")]


def test_runs_without_case_scores_are_left_out():
    matrix = model_prompt_matrix([_run("aaa", "v4", "Atlas", "1", {})])
    assert matrix.rows == []
    assert matrix.lineages == []


def test_lineages_that_never_shared_a_prompt_have_no_comparison():
    runs = [_run("old", "v4", "Atlas", "1", {"x": 1.0}), _run("new", "v5", "Atlas", "2", {"x": 0.0})]
    comparison = compare_lineages(runs, model_prompt_matrix(runs), {}, 0, 1)
    assert comparison.prompt_sha256 is None
    assert comparison.regressed == [] and comparison.improved == []


def test_comparison_uses_the_newest_prompt_both_ran():
    runs = [
        _run("old", "v4", "Atlas", "1", {"x": 1.0}),
        _run("old", "v5", "Atlas", "2", {"x": 1.0}),
        _run("new", "v4", "Atlas", "3", {"x": 1.0, "y": 1.0}),
        _run("new", "v5", "Atlas", "4", {"x": 0.5, "y": 1.0}),
    ]
    comparison = compare_lineages(runs, model_prompt_matrix(runs), {}, 0, 1)
    assert comparison.prompt_sha256 == "new"
    assert [c.case_id for c in comparison.regressed] == ["x"]
    assert comparison.unchanged_count == 1


def test_case_changes_put_the_biggest_regression_first():
    regressed, improved, unchanged = case_changes(
        {"small": 1.0, "big": 1.0, "better": 0.0, "same": 1.0},
        {"small": 0.9, "big": 0.1, "better": 1.0, "same": 1.0},
    )
    assert [c.case_id for c in regressed] == ["big", "small"]
    assert [c.case_id for c in improved] == ["better"]
    assert unchanged == 1


def test_value_detail_needs_archived_mismatches_on_both_sides():
    runs = [
        _run("aaa", "v4", "Atlas", "1", {"x": 1.0}, mismatches_file="_runs/a.yml"),
        _run("aaa", "v5", "Atlas", "2", {"x": 1.0}),
    ]
    comparison = compare_lineages(runs, model_prompt_matrix(runs), {"_runs/a.yml": {}}, 0, 1)
    assert not comparison.has_value_detail


def test_values_are_newly_wrong_or_fixed_by_case_person_and_field():
    runs = [
        _run("aaa", "v4", "Atlas", "1", {"x": 1.0}, mismatches_file="base.yml"),
        _run("aaa", "v5", "Atlas", "2", {"x": 1.0}, mismatches_file="cand.yml"),
    ]
    both = Mismatch(person="Ann", field="phone", expected="1", actual="2")
    only_baseline = Mismatch(person="Ann", field="email", expected="a@b", actual="—")
    only_candidate = Mismatch(person="Bo", field="phone", expected="3", actual="4")
    run_mismatches = {"base.yml": {"x": [both, only_baseline]}, "cand.yml": {"x": [both, only_candidate]}}
    comparison = compare_lineages(runs, model_prompt_matrix(runs), run_mismatches, 0, 1)
    assert comparison.has_value_detail
    assert [(v.person, v.field) for v in comparison.newly_wrong] == [("Bo", "phone")]
    assert [(v.person, v.field) for v in comparison.fixed] == [("Ann", "email")]


def test_default_pair_is_the_two_best_on_the_newest_prompt_with_two_scores():
    runs = [
        _run("old", "a", "P", "1", {"x": 0.5}),
        _run("old", "b", "P", "1", {"x": 0.9}),
        _run("old", "c", "P", "1", {"x": 0.7}),
        _run("new", "a", "P", "2", {"x": 1.0}),
    ]
    assert default_pair(model_prompt_matrix(runs)) == (1, 2)
