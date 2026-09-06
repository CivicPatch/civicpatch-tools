"""What pipeline runs cost, per state.

Run-grain, not changeset-grain: a run that failed before minting a changeset still spent money,
so nothing here joins `changesets` at all. Split from `changeset_summaries`, which renders it,
because it answers to a different permission — that page is signed-in, this is Maintainer-only.
"""

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
