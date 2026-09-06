"""Request bodies for the cadence and budget forms.

Split by *who may write them*, not by which form they appear in: the UI edits cadence and caps
behind one modal, but admins allocate and maintainers spend, so they are two requests with two
gates. One body would need the route to check a permission per field.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class SetCadenceRequest(BaseModel):
    """Maintainer-writable. `None` for cadence_days means manual: no schedule, and this state's
    candidates never drain on their own."""

    cadence_days: Optional[int] = Field(default=None, gt=0)
    cadence_start: Optional[date] = None


class SetCapsRequest(BaseModel):
    """Admin-writable. `None` means no cap at that scope, which is not the same as `0` — zero is
    a real setting meaning spend nothing, and it is what makes a cap usable as a stop switch."""

    pipeline_run_cap_usd: Optional[Decimal] = Field(default=None, ge=0)
    monthly_cap_usd: Optional[Decimal] = Field(default=None, ge=0)


class SetGlobalCapRequest(BaseModel):
    """Admin-writable. The ceiling for every state together — a shared one, not an allocation:
    the per-state caps may sum past it, and the UI shows that rather than refusing it."""

    monthly_cap_usd: Optional[Decimal] = Field(default=None, ge=0)
