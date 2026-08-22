"""Database queries for `source_records` — append-only evidence, one row per person.

`raw` holds every sighting behind that person; `parsed` holds the reconciliation across them.

Insert only. Both halves are write-once: a replayed parser fix writes posts/memberships and
may add a new row, but must never rewrite an existing `parsed`, which would destroy the audit
fact the row exists to hold. There is deliberately no update and no delete here.

The derivation lives in `core.source_record_parse`; this module owns the SQL.
"""

import json

from core.source_record_parse import parse_record
from database.database import get_pool
from shared.utils.taxonomy import Taxonomy


async def insert_source_records(
    request_id: str,
    jurisdiction_ocdid: str,
    records_by_person: dict[str, list[dict]],
    taxonomy: Taxonomy,
) -> int:
    """One row per person: every sighting behind them in `raw`, the reconciliation in `parsed`.

    Person-grain, not sighting-grain, because `parsed` *is* the reconciliation — `parse_record`
    takes every label and picks one winning role and one division across them. Storing a row
    per sighting would parse each label alone and throw away the decision cp.org exists to make.

    `parsed` is written at submit, not publish: review is the gate, so a reviewer has to be
    able to see the derivation it is approving.
    """
    rows = [
        (
            request_id,
            person_id,
            jurisdiction_ocdid,
            json.dumps(records),
            json.dumps(
                parse_record(
                    list(
                        dict.fromkeys(
                            record["label"] for record in records if record.get("label")
                        )
                    ),
                    jurisdiction_ocdid,
                    taxonomy,
                )
            ),
        )
        for person_id, records in records_by_person.items()
    ]
    if not rows:
        return 0

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO source_records
                (request_id, person_id, jurisdiction_ocdid, raw, parsed)
            VALUES (%s, %s, %s, %s, %s)
            """,
            rows,
        )
    return len(rows)


async def get_source_records_for_request(request_id: str) -> list[dict]:
    """What one scrape derived, oldest first."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, request_id::text, person_id, jurisdiction_ocdid,
                   raw, parsed, published_at, created_at
            FROM source_records
            WHERE request_id = %s
            ORDER BY created_at
            """,
            (request_id,),
        )
        columns = [column.name for column in cur.description or []]
        return [dict(zip(columns, row)) for row in await cur.fetchall()]
