"""What pipeline runs cost, per state.

Run-grain, not changeset-grain: a run that failed before minting a changeset still spent money,
so nothing here joins `changesets` at all. Split from `changeset_summaries`, which renders it,
because it answers to a different permission — that page is signed-in, this is Maintainer-only.
"""

from decimal import Decimal

from database.database import get_pool
from psycopg.rows import dict_row
from schemas.pipeline_run_spend import StateSpend

DEFAULT_SPEND_WINDOW_DAYS = 30

# Per *run*, not per changeset: a run that failed before minting one still spent money, and
# leaving it out would flatter exactly the states that waste the most.
#
# Two windows in one scan, so the page can say whether a state is spending more than it was.
# The scan reaches back twice the window and the FILTERs split it; running this as two queries
# would read the same rows twice.
#
# Null and absent say different things, and both are load-bearing: a **null** figure means the
# state spent nothing in *that* window, and an **absent state** means it spent nothing in
# either. Neither is 0, which would claim it scraped for free.
STATE_SPEND_SQL = """
SELECT j.state,
       sum(lc.cost_usd) FILTER (WHERE lc.created_at >= now() - %(window)s::interval) AS spend_usd,
       sum(lc.cost_usd) FILTER (WHERE lc.created_at <  now() - %(window)s::interval) AS prior_spend_usd,
       sum(lc.cost_usd) FILTER (WHERE lc.created_at >= now() - %(window)s::interval)
           / NULLIF(
               count(DISTINCT lc.pipeline_run_id)
                   FILTER (WHERE lc.created_at >= now() - %(window)s::interval),
               0
             ) AS cost_per_scrape_usd
FROM llm_calls lc
JOIN pipeline_runs pr ON pr.id = lc.pipeline_run_id
JOIN jurisdictions j USING (jurisdiction_ocdid)
WHERE lc.created_at >= now() - (%(window)s::interval * 2)
GROUP BY j.state
ORDER BY spend_usd DESC NULLS LAST
"""


async def get_state_spend(
    window_days: int = DEFAULT_SPEND_WINDOW_DAYS,
) -> list[StateSpend]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            STATE_SPEND_SQL,
            {"window": f"{window_days} days"},
        )
        return [StateSpend(**row) for row in await cur.fetchall()]


# Month to date, for the two monthly caps. The calendar month in UTC, not a rolling 30 days:
# a budget is something an operator sets against a month they can name, and a rolling window
# would let spend that was refused on the 30th become affordable again on the 31st.
#
# One statement for both scopes. The state figure and the fleet figure are the same sum over
# different row sets, and reading them separately is how they come to disagree about which month
# it is at a boundary.
MONTH_TO_DATE_SQL = """
SELECT
    COALESCE(sum(lc.cost_usd) FILTER (WHERE j.state = %(state)s), 0) AS state_spent,
    COALESCE(sum(lc.cost_usd), 0)                                    AS global_spent
FROM llm_calls lc
JOIN pipeline_runs pr ON pr.id = lc.pipeline_run_id
JOIN jurisdictions j USING (jurisdiction_ocdid)
WHERE lc.created_at >= date_trunc('month', now() AT TIME ZONE 'utc')
"""


async def get_month_to_date_spend(state: str) -> tuple[Decimal, Decimal]:
    """`(this state's spend, everything's spend)` so far this calendar month.

    Zero here, unlike everywhere else in this module, is the honest answer: "nothing spent yet"
    is what a budget check needs, and the caller compares it against a cap rather than
    displaying it as a cost.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(MONTH_TO_DATE_SQL, {"state": state})
        row = await cur.fetchone()
    assert row, "MONTH_TO_DATE_SQL aggregates, so it always returns one row"
    return row[0], row[1]
