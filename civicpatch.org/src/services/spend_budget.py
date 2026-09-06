"""Whether a state may spend any more this month.

Orchestration only: two reads and one pure decision. The decision itself is
`core.spend_limits.cap_reached`, which knows nothing about the database.

Read at the moment of asking, never cached. A cap is something an admin changes *because*
spending is running away, and a cached answer would keep dispatching for as long as the cache
lived.
"""

from core.spend_limits import Cap, cap_reached
from database.pipeline_run_spend import get_month_to_date_spend
from database.state_settings import get_global_settings, get_state_settings


async def cap_reached_for_state(state: str) -> Cap | None:
    state_spent, global_spent = await get_month_to_date_spend(state)
    settings = await get_state_settings(state)
    fleet = await get_global_settings()
    return cap_reached(
        state_spent, settings.monthly_cap_usd, global_spent, fleet.monthly_cap_usd
    )
