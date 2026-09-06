"""What each LLM call cost, as its provider stated it.

Written once per run, from the `costs.json` the pipeline submits with its artifacts. Nothing
here computes a cost: the price table this replaced fell through to zero for any
(model, provider) pair nobody had listed, so a model bump reported free work.
"""

import logging

from psycopg import sql

from database.database import get_pool
from shared.schemas import LLMCall

logger = logging.getLogger(__name__)

# Derived, not restated. These are the columns `costs.json` carries because the pipeline writes
# that file from this very model — so a field added to `LLMCall` reaches the table instead of
# being silently dropped here, which two hand-kept lists could not promise.
#
# Read with `[]`, not `.get()`: a missing key would insert an explicit NULL rather than falling
# back to the column default, so half these columns would raise NotNullViolation anyway. A shape
# mismatch should say so, and the caller already logs it.
_COLUMNS = tuple(LLMCall.model_fields)


async def record_calls(pipeline_run_id: str, calls: list[dict]) -> int:
    """Returns how many rows landed — not how many were offered.

    Submit is an HTTP endpoint, so a scraper that retries after a timeout the server actually
    completed re-sends the same calls. They conflict on `(pipeline_run_id, generation_id)` and
    are skipped, which is why the caller logs this count rather than assuming one.
    """
    # Grounded Google calls state no cost — grounding is sold on a quota, so a per-call figure
    # is not even well defined. They stay in `costs.json` for the token counts and out of here,
    # rather than being written as a zero that would read as free.
    calls = [call for call in calls if call.get("cost_usd") is not None]
    if not calls:
        return 0

    # Composed rather than f-strung: the column list is built at runtime, so an f-string is a
    # `str` and psycopg only accepts a `LiteralString`. `sql.Identifier` also quotes the names.
    names = ("pipeline_run_id", *_COLUMNS)
    statement = sql.SQL(
        "INSERT INTO llm_calls ({columns}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    ).format(
        columns=sql.SQL(", ").join(sql.Identifier(name) for name in names),
        placeholders=sql.SQL(", ").join(sql.Placeholder() * len(names)),
    )
    rows = [
        (pipeline_run_id, *(call[column] for column in _COLUMNS)) for call in calls
    ]

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(statement, rows)
        recorded = cur.rowcount
        await conn.commit()
    return recorded
