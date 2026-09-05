"""What each LLM call cost, as its provider stated it.

Written once per run, from the `costs.json` the pipeline submits with its artifacts. Nothing
here computes a cost: the price table this replaced fell through to zero for any
(model, provider) pair nobody had listed, so a model bump reported free work.
"""

import logging

from psycopg import sql

from database.database import get_pool

logger = logging.getLogger(__name__)

# The row as `costs.json` carries it — every key, because the pipeline writes the file from
# `LLMCall.model_dump()`. Read with `[]`, not `.get()`: a missing key would insert an explicit
# NULL rather than falling back to the column default, so half these columns would raise
# NotNullViolation anyway. A shape mismatch should say so, and the caller already logs it.
_COLUMNS = (
    "prompt_name",
    "source_url",
    "chunk_index",
    "chunk_count",
    "attempt",
    "seed",
    "gateway",
    "model",
    "routed_model",
    "upstream_provider",
    "generation_id",
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "cost_usd",
    "web_search",
    "duration_ms",
    "finish_reason",
    "error",
)


async def record_calls(pipeline_run_id: str, calls: list[dict]) -> int:
    """Returns how many rows landed, so the caller can log a count it did not assume."""
    # Grounded Google calls state no cost — grounding is sold on a quota, so a per-call figure
    # is not even well defined. They stay in `costs.json` for the token counts and out of here,
    # rather than being written as a zero that would read as free.
    calls = [call for call in calls if call.get("cost_usd") is not None]
    if not calls:
        return 0

    # Composed rather than f-strung: the column list is built at runtime, so an f-string is a
    # `str` and psycopg only accepts a `LiteralString`. `sql.Identifier` also quotes the names.
    names = ("pipeline_run_id", *_COLUMNS)
    statement = sql.SQL("INSERT INTO llm_calls ({columns}) VALUES ({placeholders})").format(
        columns=sql.SQL(", ").join(sql.Identifier(name) for name in names),
        placeholders=sql.SQL(", ").join(sql.Placeholder() * len(names)),
    )
    rows = [
        (pipeline_run_id, *(call[column] for column in _COLUMNS)) for call in calls
    ]

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(statement, rows)
        await conn.commit()
    return len(rows)
