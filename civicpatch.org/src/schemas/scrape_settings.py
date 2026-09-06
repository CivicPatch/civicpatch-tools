"""Request bodies for the cadence and budget forms.

Two requests behind one form: cadence and caps are written separately so saving one cannot
silently clear the other, which a whole-row upsert would.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class SetCadenceRequest(BaseModel):
    """`None` for cadence_days means manual: no schedule, and this state's candidates never
    drain on their own."""

    cadence_days: Optional[int] = Field(default=None, gt=0)
    # Which day the cadence lands on. Sep 1 with a 30-day cadence gives Sep 1, Oct 1,
    # Nov 1 — and Aug 2 before that, because the anchor picks the day in the cycle rather
    # than the day it starts.
    cadence_anchor: Optional[date] = None


class SetCapsRequest(BaseModel):
    """`None` means no cap at that scope, which is not the same as `0` — zero is a real setting
    meaning spend nothing, and it is what makes a cap usable as a stop switch."""

    pipeline_run_cap_usd: Optional[Decimal] = Field(default=None, ge=0)
    monthly_cap_usd: Optional[Decimal] = Field(default=None, ge=0)


class SetGlobalCapRequest(BaseModel):
    """The ceiling for every state together — a shared one, not an allocation:
    the per-state caps may sum past it, and the UI shows that rather than refusing it."""

    monthly_cap_usd: Optional[Decimal] = Field(default=None, ge=0)


class StateScrapePanel(BaseModel):
    """Everything the state's settings block shows, in one response.

    One call, not five: the block renders as a unit and five requests would let it paint in
    pieces, each arriving to a slightly different moment — the spend from one instant against a
    cap read at another.
    """

    state: str
    cadence_days: Optional[int] = None
    cadence_anchor: Optional[date] = None
    # Computed from the cadence, not read back from Temporal: the arithmetic is the same, and
    # asking would be a round-trip per state that is also wrong while a schedule is unconverged.
    # None means manual, which has no next run.
    next_run_at: Optional[datetime] = None

    pipeline_run_cap_usd: Optional[Decimal] = None
    monthly_cap_usd: Optional[Decimal] = None
    global_monthly_cap_usd: Optional[Decimal] = None

    # Month to date. Zero is honest here, unlike the spend column on the changesets page: this
    # is a figure measured against a ceiling, not a cost being reported.
    spent_this_month_usd: Decimal
    global_spent_this_month_usd: Decimal
    # Which cap is already reached, if either — `state_month`, `global_month`, or None.
    cap_reached: Optional[str] = None

    # Runs that stopped at their per-run ceiling this month. One is noise; a third of the
    # state's runs means the cap is set below what its pages cost.
    cost_cap_hits_this_month: int
    # What the next pass would pick up, right now.
    candidates_due: int


class GlobalScrapePanel(BaseModel):
    monthly_cap_usd: Optional[Decimal] = None
    spent_this_month_usd: Decimal
    # SUM of every state's monthly cap. May exceed the cap above; the block says so.
    state_monthly_caps_usd: Decimal
