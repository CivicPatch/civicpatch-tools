"""Database queries for roster comparison drafts: an upload sent in batches, before it is compared.

Every read and write takes the owner and skips expired drafts, so a draft id alone reaches nothing.
"""

import json
from datetime import timedelta

from psycopg.rows import dict_row

from database.database import get_pool
from schemas.roster_comparisons import RosterComparisonDraft, RosterComparisonHeader, UploadedRow

DRAFT_LIFETIME = timedelta(hours=24)

_DRAFT_COLUMNS = """
    id::text AS id, row_count AS rows,
    to_char((created_at + %(lifetime)s) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00' AS expires_at
"""


async def insert_roster_comparison_draft(owner_user_id: str, header: RosterComparisonHeader) -> RosterComparisonDraft:
    """Also clears every expired draft, so abandoned ones never pile up."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "DELETE FROM roster_comparison_drafts WHERE created_at <= now() - %s", (DRAFT_LIFETIME,)
        )
        await cur.execute(
            f"""
            INSERT INTO roster_comparison_drafts (owner_user_id, state, source_columns, corrections)
            VALUES (%(owner)s, %(state)s, %(source_columns)s, %(corrections)s)
            RETURNING {_DRAFT_COLUMNS}
            """,
            {
                "owner": owner_user_id,
                "state": header.state,
                "source_columns": json.dumps(header.source_columns),
                "corrections": json.dumps(header.corrections),
                "lifetime": DRAFT_LIFETIME,
            },
        )
        row = await cur.fetchone()
        await conn.commit()
    assert row is not None
    return RosterComparisonDraft.model_validate(row)


async def append_roster_comparison_draft_rows(
    draft_id: str, owner_user_id: str, rows: list[UploadedRow], max_rows: int
) -> RosterComparisonDraft | None:
    """None when the draft is missing, expired, someone else's, or the rows would pass `max_rows`."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            f"""
            UPDATE roster_comparison_drafts
            SET rows = rows || %(rows)s::jsonb, row_count = row_count + %(added)s
            WHERE id = %(id)s AND owner_user_id = %(owner)s
              AND created_at > now() - %(lifetime)s
              AND row_count + %(added)s <= %(max_rows)s
            RETURNING {_DRAFT_COLUMNS}
            """,
            {
                "rows": json.dumps([row.model_dump(mode="json") for row in rows]),
                "added": len(rows),
                "id": draft_id,
                "owner": owner_user_id,
                "lifetime": DRAFT_LIFETIME,
                "max_rows": max_rows,
            },
        )
        row = await cur.fetchone()
        await conn.commit()
    return None if row is None else RosterComparisonDraft.model_validate(row)


async def get_roster_comparison_draft(
    draft_id: str, owner_user_id: str
) -> tuple[RosterComparisonHeader, list[UploadedRow], int] | None:
    """The header, the rows so far and their count; None when missing, expired or someone else's."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT state, source_columns, corrections, rows, row_count
            FROM roster_comparison_drafts
            WHERE id = %s AND owner_user_id = %s AND created_at > now() - %s
            """,
            (draft_id, owner_user_id, DRAFT_LIFETIME),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    header = RosterComparisonHeader.model_validate(
        {key: row[key] for key in ("state", "source_columns", "corrections")}
    )
    return header, [UploadedRow.model_validate(uploaded) for uploaded in row["rows"]], row["row_count"]


async def delete_roster_comparison_draft(draft_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM roster_comparison_drafts WHERE id = %s", (draft_id,))
        await conn.commit()
