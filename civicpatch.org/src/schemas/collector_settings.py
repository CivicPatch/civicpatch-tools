from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field
from shared.utils.statuses import PipelineRunKind


class CollectorSettings(BaseModel):
    """One charter collector's spend bounds, apart from the scrape's `state_settings`."""

    kind: PipelineRunKind
    # Never none: a runaway jurisdiction must stop.
    pipeline_run_cap_usd: Decimal
    # None is no monthly cap at all; 0 is a real cap meaning spend nothing.
    monthly_cap_usd: Optional[Decimal]
    updated_by_user_id: Optional[str]
    updated_at: datetime


class SetCollectorCapsRequest(BaseModel):
    pipeline_run_cap_usd: Decimal = Field(ge=0)
    monthly_cap_usd: Optional[Decimal] = Field(ge=0)


class CollectorPanel(BaseModel):
    """One collector kind's row on the Pipelines page, in one response like a state's."""

    settings: CollectorSettings
    spent_this_month_usd: Decimal
    # None when no run has stated a cost to average.
    cost_per_run_this_month_usd: Optional[Decimal]
    runs_this_month: int
    cost_cap_hits_this_month: int
