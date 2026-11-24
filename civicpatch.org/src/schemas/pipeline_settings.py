from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field
from shared.utils.statuses import PipelineRunKind

# How old a place's last attempt may get before it is due again, where its state set no cadence. The
# scrape's rosters change any month; a charter only by act. Pipeline 2 is due when its law is newer.
DEFAULT_CADENCE_DAYS: dict[PipelineRunKind, int | None] = {
    PipelineRunKind.PEOPLE_COLLECTOR: 30,
    PipelineRunKind.GOVERNING_LAW_COLLECTOR: 365,
    PipelineRunKind.ORGANIZATIONS_COLLECTOR: None,
}

# A run's cap where its state set none. The scrape's None inherits pipeline.yml; a collector's is
# never none, since a runaway jurisdiction must stop.
DEFAULT_RUN_CAP_USD: dict[PipelineRunKind, Decimal | None] = {
    PipelineRunKind.PEOPLE_COLLECTOR: None,
    PipelineRunKind.GOVERNING_LAW_COLLECTOR: Decimal("0.50"),
    PipelineRunKind.ORGANIZATIONS_COLLECTOR: Decimal("0.50"),
}


class PipelineSettings(BaseModel):
    """One pipeline's cadence and money in one state. A missing row reads as this with every optional
    field None: no schedule, the kind's default run cap, no monthly cap. Zero is a real cap, "spend
    nothing", which None cannot express."""

    state: str
    kind: PipelineRunKind
    # None = manual: no schedule. The candidates' due age then falls back to the kind's default.
    cadence_days: int | None = None
    # Which day the cadence lands on, so states stagger instead of firing at one midnight.
    cadence_anchor: date | None = None
    pipeline_run_cap_usd: Decimal | None = None
    monthly_cap_usd: Decimal | None = None
    updated_by_user_id: str | None = None
    updated_at: datetime | None = None


class GlobalSettings(BaseModel):
    """The monthly cap over every pipeline in every state: a shared ceiling, not an allocation, so the
    per-pipeline caps may add up past it."""

    monthly_cap_usd: Decimal | None = None
    updated_by_user_id: str | None = None
    updated_at: datetime | None = None


class SetCadenceRequest(BaseModel):
    """None for cadence_days means manual: no schedule."""

    cadence_days: int | None = Field(default=None, gt=0)
    cadence_anchor: date | None = None


class SetCapsRequest(BaseModel):
    """None means the default (run cap) or no cap (monthly), not 0: zero is a real cap, spend nothing."""

    pipeline_run_cap_usd: Decimal | None = Field(default=None, ge=0)
    monthly_cap_usd: Decimal | None = Field(default=None, ge=0)


class SetGlobalCapRequest(BaseModel):
    """Every pipeline in every state together: a shared ceiling, not an allocation."""

    monthly_cap_usd: Decimal | None = Field(default=None, ge=0)


class PipelinePanel(BaseModel):
    """Everything one pipeline's settings block in one state shows, in one response, so spend and
    caps are read at one moment."""

    state: str
    kind: PipelineRunKind
    cadence_days: int | None = None
    cadence_anchor: date | None = None
    # Computed from the cadence, not read back from Temporal. None means manual.
    next_run_at: datetime | None = None
    pipeline_run_cap_usd: Decimal | None = None
    monthly_cap_usd: Decimal | None = None
    global_monthly_cap_usd: Decimal | None = None
    # Month to date: zero is honest here, a figure measured against a ceiling.
    spent_this_month_usd: Decimal
    global_spent_this_month_usd: Decimal
    # `state_month`, `global_month`, or None.
    cap_reached: str | None = None
    # None means no runs this month, never a free one.
    cost_per_run_this_month_usd: Decimal | None = None
    cost_cap_hits_this_month: int
    # What the next pass would pick up, right now.
    candidates_due: int


class GlobalPanel(BaseModel):
    monthly_cap_usd: Decimal | None = None
    spent_this_month_usd: Decimal
    # Every monthly cap summed; may exceed the cap above, and the page says so.
    monthly_caps_usd: Decimal
    # The scrape's, month to date. None means no runs to average.
    cost_per_run_this_month_usd: Decimal | None = None
    seconds_per_run_this_month: int | None = None
    pipeline_run_concurrency: int

