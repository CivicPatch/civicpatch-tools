"""What pipeline runs cost, in money and in time.

Run-grain, not changeset-grain: a run that failed before minting a changeset still spent money,
so nothing here joins `changesets` at all.
"""

from decimal import Decimal

from database.database import get_pool
from shared.utils.statuses import PipelineRunStatus

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


# Per run, not per call, and null rather than zero when the state has not run this month.
MONTH_TO_DATE_COST_PER_RUN_SQL = """
SELECT sum(lc.cost_usd) / NULLIF(count(DISTINCT lc.pipeline_run_id), 0)
FROM llm_calls lc
JOIN pipeline_runs pr ON pr.id = lc.pipeline_run_id
JOIN jurisdictions j USING (jurisdiction_ocdid)
WHERE j.state = %(state)s
  AND lc.created_at >= date_trunc('month', now() AT TIME ZONE 'utc')
"""


async def get_month_to_date_cost_per_run(state: str) -> Decimal | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(MONTH_TO_DATE_COST_PER_RUN_SQL, {"state": state})
        row = await cur.fetchone()
    assert row, "MONTH_TO_DATE_COST_PER_RUN_SQL aggregates, so it always returns one row"
    return row[0]


FLEET_MONTH_TO_DATE_COST_PER_RUN_SQL = """
SELECT sum(cost_usd) / NULLIF(count(DISTINCT pipeline_run_id), 0)
FROM llm_calls
WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'utc')
"""


async def get_fleet_month_to_date_cost_per_run() -> Decimal | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(FLEET_MONTH_TO_DATE_COST_PER_RUN_SQL)
        row = await cur.fetchone()
    assert row, "FLEET_MONTH_TO_DATE_COST_PER_RUN_SQL aggregates, so it always returns one row"
    return row[0]


# SUCCESS only: the stale-run sweep stamps finished_at when it gives up, hours after the run died.
FLEET_MONTH_TO_DATE_SECONDS_PER_RUN_SQL = """
SELECT round(extract(epoch FROM avg(finished_at - created_at)))::int
FROM pipeline_runs
WHERE status = %(status)s
  AND finished_at >= date_trunc('month', now() AT TIME ZONE 'utc')
"""


async def get_fleet_month_to_date_seconds_per_run() -> int | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            FLEET_MONTH_TO_DATE_SECONDS_PER_RUN_SQL,
            {"status": PipelineRunStatus.SUCCESS.value},
        )
        row = await cur.fetchone()
    assert row, "FLEET_MONTH_TO_DATE_SECONDS_PER_RUN_SQL aggregates, so it always returns one row"
    return row[0]
