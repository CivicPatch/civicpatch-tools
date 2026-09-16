"""The JSON that dashboard/*.js renders."""

from typing import Literal

from pydantic import BaseModel

from eval_records import CaseMismatches, MismatchValue


class CaseCount(BaseModel):
    case_id: str
    count: int


class GateFailure(BaseModel):
    metric: str
    cases: list[CaseCount]


class ProviderVerdict(BaseModel):
    provider: str
    blocked: bool
    gate_failures: list[GateFailure]
    failed_case_ids: list[str]
    cases_passed: int | None
    cases_total: int | None
    priority_scores: dict[str, float]
    cost_usd: float | None
    ran_at: str | None


class TrendPoint(BaseModel):
    timestamp: str
    prompt_sha256: str
    score: float


class TrendSeries(BaseModel):
    provider: str
    points: list[TrendPoint]


class TrendChart(BaseModel):
    metric: str
    is_priority: bool
    gate_floor: float | None
    series: list[TrendSeries]


class EvalTrends(BaseModel):
    providers: list[str]
    charts: list[TrendChart]
    run_count: int


IssueKind = Literal["cases_failed", "gate_failed", "many_missing", "wide_swing"]


class Issue(BaseModel):
    kind: IssueKind
    severity: int
    eval_name: str
    provider: str
    metric: str | None = None
    score: float | None = None
    gate_floor: float | None = None
    missing_count: int | None = None
    expected_count: int | None = None
    swing: float | None = None
    failed_case_ids: list[str] = []


class Lineage(BaseModel):
    model: str
    provider: str


class MatrixCell(BaseModel):
    mean_score: float
    run_count: int
    mean_cost_usd: float | None


class MatrixRow(BaseModel):
    prompt_sha256: str
    cells: list[MatrixCell | None]


class ModelPromptMatrix(BaseModel):
    lineages: list[Lineage]
    rows: list[MatrixRow]


class CaseChange(BaseModel):
    case_id: str
    baseline_score: float
    candidate_score: float


class ValueChange(BaseModel):
    """`actual` is the wrong answer, from whichever side got it wrong."""

    case_id: str
    person: str
    field: str
    expected: MismatchValue
    actual: MismatchValue


class LineageComparison(BaseModel):
    baseline_index: int  # into ModelPromptMatrix.lineages
    candidate_index: int
    prompt_sha256: str | None
    baseline: MatrixCell | None
    candidate: MatrixCell | None
    regressed: list[CaseChange]
    improved: list[CaseChange]
    unchanged_count: int
    has_value_detail: bool
    newly_wrong: list[ValueChange]
    fixed: list[ValueChange]


class ModelComparison(BaseModel):
    default_baseline_index: int
    default_candidate_index: int
    pairs: list[LineageComparison]


DiffLineKind = Literal["added", "removed", "context"]


class DiffLine(BaseModel):
    kind: DiffLineKind
    text: str


class RunSummary(BaseModel):
    timestamp: str
    provider: str
    scores: dict[str, float]


class PromptVersion(BaseModel):
    prompt_sha256: str
    text: str
    first_run_at: str
    last_run_at: str
    providers: list[str]
    runs: list[RunSummary]
    previous_sha256: str | None
    diff: list[DiffLine]


class MetricCell(BaseModel):
    score: float | None
    swing_is_wide: bool
    half_swing: float
    missing_count: int | None


class MetricRow(BaseModel):
    metric: str
    cells: list[MetricCell | None]


CaseStability = Literal["steady", "moves", "unknown"]


class CaseRow(BaseModel):
    case_id: str
    scores: list[float | None]
    stability: CaseStability


class CaseMovement(BaseModel):
    provider: str
    regressed: list[str]
    improved: list[str]


class EvalDetail(BaseModel):
    providers: list[str]
    metric_rows: list[MetricRow]
    case_providers: list[str]
    case_rows: list[CaseRow]
    movements: list[CaseMovement]


class EvalSection(BaseModel):
    eval_name: str
    dataset_dir: str
    verdicts: list[ProviderVerdict]
    matrix: ModelPromptMatrix
    comparison: ModelComparison | None
    trends: EvalTrends
    prompt_versions: list[PromptVersion]
    detail: EvalDetail | None
    latest_mismatches: dict[str, CaseMismatches]


class DashboardPayload(BaseModel):
    evals: list[EvalSection]
    issues: list[Issue]
