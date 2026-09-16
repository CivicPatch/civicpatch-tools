from pydantic import BaseModel

OPEN_ROUTER_PREFIX = "open_router-"

MismatchValue = str | list[str] | None


def short_provider(provider: str) -> str:
    return provider.replace(OPEN_ROUTER_PREFIX, "")


class Mismatch(BaseModel):
    person: str
    field: str
    expected: MismatchValue = None
    actual: MismatchValue = None
    expected_label: str | None = None
    actual_label: str | None = None


CaseMismatches = dict[str, list[Mismatch]]


class HistoryRun(BaseModel):
    """A row of history.yml as eval_utils.record_history writes it."""

    timestamp: str = ""
    provider: str = ""
    model: str | None = None
    prompt_sha256: str | None = None
    cost_usd: float | None = None
    scores: dict[str, float] = {}
    cases: dict[str, float] = {}
    mismatches_file: str | None = None

    @property
    def short_provider(self) -> str:
        return short_provider(self.provider)

    @property
    def mean_case_score(self) -> float | None:
        if not self.cases:
            return None
        return sum(self.cases.values()) / len(self.cases)


class MetricResult(BaseModel):
    eval_name: str
    provider: str
    metric: str
    f1: float | None
    correct: int | None
    missing: int | None
    cost_usd: float | None
    ran_at: str | None


class CaseTally(BaseModel):
    eval_name: str
    provider: str
    passed: int
    total: int | None
    failed_case_ids: list[str]
    cost_usd: float | None
    ran_at: str | None

    @property
    def score(self) -> float | None:
        return self.passed / self.total if self.total else None


class EvalResults(BaseModel):
    metrics: list[MetricResult]
    case_tallies: list[CaseTally] = []

    def metrics_for(self, provider: str) -> list[MetricResult]:
        return [r for r in self.metrics if r.provider == provider]

    def metric_for(self, provider: str, metric: str) -> MetricResult | None:
        return next((r for r in self.metrics if r.provider == provider and r.metric == metric), None)

    def tally_for(self, provider: str) -> CaseTally | None:
        return next((t for t in self.case_tallies if t.provider == provider), None)

    @property
    def providers(self) -> list[str]:
        return sorted({r.provider for r in self.metrics} | {t.provider for t in self.case_tallies})
