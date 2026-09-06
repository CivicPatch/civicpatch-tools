from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class StateSettings(BaseModel):
    """One state's cadence and its money.

    **Every optional field means *inherit* or *none*, never zero.** That is what lets the page
    say `manual` and `$0.20 default` without a second flag to tell those apart. Zero is legal
    everywhere it appears and means "spend nothing", which is a real setting NULL cannot express.

    A state with no row is identical to a row of all-NULL, so nothing seeds fifty rows and
    `get_state_settings` answers for a state that has never been configured.
    """

    state: str
    # NULL = manual: no schedule, and the scrape candidates for this state never drain on their
    # own. The page's own word for it.
    cadence_days: int | None = None
    # Staggers the states, so fifty schedules do not all fire at midnight.
    cadence_start: date | None = None
    # One run's cap. NULL = inherit the pipeline's own default.
    pipeline_run_cap_usd: Decimal | None = None
    # This state's calendar month. NULL = no cap.
    monthly_cap_usd: Decimal | None = None
    updated_by_user_id: str | None = None
    updated_at: datetime | None = None


class GlobalSettings(BaseModel):
    """The monthly cap for everything, across every state.

    Same field name as `StateSettings.monthly_cap_usd` on purpose: one concept at two scopes,
    told apart by which model it is on.

    A **shared cap, not an allocation**: states draw from it first-come, and each state's own
    monthly cap is what stops one state emptying it. `SUM(state_settings.monthly_cap_usd)` may
    therefore exceed it — a normal state, meaning *these caps are caps, not reservations* —
    and the UI says so rather than refusing it.
    """

    monthly_cap_usd: Decimal | None = None
    updated_by_user_id: str | None = None
    updated_at: datetime | None = None
