"""A lineage is a model on a provider; two are only compared on a prompt both ran."""

from itertools import permutations
from statistics import mean

from aggregation import SAME_SCORE, group_by, mean_by_key
from dashboard_schema import (
    CaseChange,
    Lineage,
    LineageComparison,
    MatrixCell,
    MatrixRow,
    ModelComparison,
    ModelPromptMatrix,
    ValueChange,
)
from eval_records import CaseMismatches, HistoryRun

UNKNOWN_MODEL = "unknown model"


def lineage_of(run: HistoryRun) -> Lineage:
    return Lineage(model=run.model or UNKNOWN_MODEL, provider=run.short_provider)


def _scored_runs(runs: list[HistoryRun], lineage: Lineage, sha: str) -> list[HistoryRun]:
    return [r for r in runs if r.prompt_sha256 == sha and lineage_of(r) == lineage and r.mean_case_score is not None]


def _matrix_cell(runs: list[HistoryRun]) -> MatrixCell | None:
    scores = [r.mean_case_score for r in runs if r.mean_case_score is not None]
    if not scores:
        return None
    costs = [r.cost_usd for r in runs if r.cost_usd is not None]
    return MatrixCell(mean_score=mean(scores), run_count=len(scores), mean_cost_usd=mean(costs) if costs else None)


def model_prompt_matrix(runs: list[HistoryRun]) -> ModelPromptMatrix:
    scored = [r for r in runs if r.mean_case_score is not None and r.prompt_sha256]
    keys = sorted({(lineage.model, lineage.provider) for lineage in map(lineage_of, scored)})
    lineages = [Lineage(model=model, provider=provider) for model, provider in keys]
    by_prompt = group_by(scored, lambda r: r.prompt_sha256)
    newest_first = sorted(by_prompt, key=lambda sha: max(r.timestamp for r in by_prompt[sha]), reverse=True)
    rows = [
        MatrixRow(prompt_sha256=sha, cells=[_matrix_cell(_scored_runs(by_prompt[sha], lineage, sha)) for lineage in lineages])
        for sha in newest_first
    ]
    return ModelPromptMatrix(lineages=lineages, rows=rows)


def shared_prompt(matrix: ModelPromptMatrix, baseline_index: int, candidate_index: int) -> str | None:
    return next(
        (row.prompt_sha256 for row in matrix.rows if row.cells[baseline_index] and row.cells[candidate_index]),
        None,
    )


def _score_delta(change: CaseChange) -> float:
    return change.candidate_score - change.baseline_score


def case_changes(baseline: dict[str, float], candidate: dict[str, float]) -> tuple[list[CaseChange], list[CaseChange], int]:
    """Regressed worst first, improved best first."""
    changes = [
        CaseChange(case_id=case_id, baseline_score=baseline[case_id], candidate_score=candidate[case_id])
        for case_id in sorted(baseline.keys() & candidate.keys())
    ]
    regressed = sorted((c for c in changes if _score_delta(c) < -SAME_SCORE), key=_score_delta)
    improved = sorted((c for c in changes if _score_delta(c) > SAME_SCORE), key=_score_delta, reverse=True)
    return regressed, improved, len(changes) - len(regressed) - len(improved)


def _value_changes(wrong_here: CaseMismatches, wrong_there: CaseMismatches) -> list[ValueChange]:
    there = {(case_id, m.person, m.field) for case_id, rows in wrong_there.items() for m in rows}
    return [
        ValueChange(case_id=case_id, person=m.person, field=m.field, expected=m.expected, actual=m.actual)
        for case_id, rows in sorted(wrong_here.items())
        for m in rows
        if (case_id, m.person, m.field) not in there
    ]


def _latest_mismatches(runs: list[HistoryRun], run_mismatches: dict[str, CaseMismatches]) -> CaseMismatches | None:
    archived = [r for r in runs if r.mismatches_file in run_mismatches]
    if not archived:
        return None
    return run_mismatches[max(archived, key=lambda r: r.timestamp).mismatches_file]


def compare_lineages(
    runs: list[HistoryRun],
    matrix: ModelPromptMatrix,
    run_mismatches: dict[str, CaseMismatches],
    baseline_index: int,
    candidate_index: int,
) -> LineageComparison:
    sha = shared_prompt(matrix, baseline_index, candidate_index)
    baseline_runs = _scored_runs(runs, matrix.lineages[baseline_index], sha) if sha else []
    candidate_runs = _scored_runs(runs, matrix.lineages[candidate_index], sha) if sha else []
    regressed, improved, unchanged = case_changes(
        mean_by_key(r.cases for r in baseline_runs), mean_by_key(r.cases for r in candidate_runs)
    )
    baseline_wrong = _latest_mismatches(baseline_runs, run_mismatches)
    candidate_wrong = _latest_mismatches(candidate_runs, run_mismatches)
    has_value_detail = baseline_wrong is not None and candidate_wrong is not None
    return LineageComparison(
        baseline_index=baseline_index,
        candidate_index=candidate_index,
        prompt_sha256=sha,
        baseline=_matrix_cell(baseline_runs),
        candidate=_matrix_cell(candidate_runs),
        regressed=regressed,
        improved=improved,
        unchanged_count=unchanged,
        has_value_detail=has_value_detail,
        newly_wrong=_value_changes(candidate_wrong, baseline_wrong) if has_value_detail else [],
        fixed=_value_changes(baseline_wrong, candidate_wrong) if has_value_detail else [],
    )


def default_pair(matrix: ModelPromptMatrix) -> tuple[int, int]:
    """Best as the baseline, runner-up as the candidate."""
    for row in matrix.rows:
        ranked = sorted(((cell.mean_score, index) for index, cell in enumerate(row.cells) if cell), reverse=True)
        if len(ranked) >= 2:
            return ranked[0][1], ranked[1][1]
    return 0, 1


def model_comparison(
    runs: list[HistoryRun], matrix: ModelPromptMatrix, run_mismatches: dict[str, CaseMismatches]
) -> ModelComparison | None:
    if len(matrix.lineages) < 2:
        return None
    baseline_index, candidate_index = default_pair(matrix)
    return ModelComparison(
        default_baseline_index=baseline_index,
        default_candidate_index=candidate_index,
        pairs=[
            compare_lineages(runs, matrix, run_mismatches, b, c)
            for b, c in permutations(range(len(matrix.lineages)), 2)
        ],
    )
