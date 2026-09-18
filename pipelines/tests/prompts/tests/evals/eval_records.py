from pydantic import AliasChoices, BaseModel, ConfigDict, Field

OPEN_ROUTER_PREFIX = "open_router-"

# `bool` first: the page-coverage eval's answers are yes/no, and with `str` first pydantic
# renders them as "True"/"False" in the dashboard rather than as booleans.
MismatchValue = bool | str | list[str] | None


def short_provider(provider: str) -> str:
    return provider.replace(OPEN_ROUTER_PREFIX, "")


class Mismatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # What the row is about: a person for the officials eval, a body for page coverage, a url or
    # `page` for the page-relevance eval. Reads `person` too, because every run recorded before
    # the three suites shared this model wrote that name and history is not rewritten.
    subject: str = Field(validation_alias=AliasChoices("subject", "person"))
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
    # Set when the provider produced no numbers at all: a timeout or a refusal, recorded so the
    # run shows a failure rather than a provider that silently stopped appearing.
    error: str | None = None

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
