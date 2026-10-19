from pydantic import BaseModel

from database.database import get_pool
from shared.schemas import GoverningLaw
from shared.utils.statuses import PipelineRunKind


class GoverningLawRow(BaseModel):
    """One active jurisdiction, with what it has: None until a collector run has written it."""

    jurisdiction_ocdid: str
    name: str
    governing_law: GoverningLaw | None


async def get_governing_law_row(jurisdiction_ocdid: str) -> GoverningLawRow | None:
    """None for an unknown or inactive jurisdiction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, data->>'name', extras_governing_law
            FROM jurisdictions
            WHERE jurisdiction_ocdid = %s AND status = 'active'
            """,
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return GoverningLawRow(
        jurisdiction_ocdid=row[0],
        name=row[1] or "",
        governing_law=GoverningLaw.model_validate(row[2]) if row[2] is not None else None,
    )


async def save_governing_law(cur, jurisdiction_ocdid: str, governing_law: GoverningLaw) -> None:
    await cur.execute(
        "UPDATE jurisdictions SET extras_governing_law = %s::jsonb WHERE jurisdiction_ocdid = %s",
        (governing_law.model_dump_json(), jurisdiction_ocdid),
    )


class CollectionCandidate(BaseModel):
    jurisdiction_ocdid: str
    name: str


# A year, then a jurisdiction's governing law is collected again: charters change by act.
_COLLECT_AGAIN_AFTER = "365 days"
# A run that failed is not retried within the same day's batch.
_TRIED_WITHIN = "1 day"


async def get_collection_candidates(state: str, limit: int | None) -> list[CollectionCandidate]:
    """The state's jurisdictions below the state with no governing law yet, or only a year-old
    one, and no collection in flight or tried in the last day. Never-collected first."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT j.jurisdiction_ocdid, j.data->>'name'
            FROM jurisdictions j
            WHERE j.state = %s AND j.status = 'active' AND j.level <> 'state'
              AND (j.extras_governing_law IS NULL
                   OR (j.extras_governing_law->>'collected_at')::timestamptz < now() - interval '{_COLLECT_AGAIN_AFTER}')
                -- Tried in the last day, finished or not: a failing place is not claimed again and again.
              AND NOT EXISTS (
                  SELECT 1 FROM pipeline_runs r
                  WHERE r.jurisdiction_ocdid = j.jurisdiction_ocdid AND r.kind = %s
                    AND (r.finished_at IS NULL OR r.created_at >= now() - interval '{_TRIED_WITHIN}')
              )
            ORDER BY j.extras_governing_law IS NOT NULL, j.jurisdiction_ocdid
            LIMIT %s
            """,
            (state, PipelineRunKind.GOVERNING_LAW_COLLECTOR, limit),
        )
        return [CollectionCandidate(jurisdiction_ocdid=row[0], name=row[1] or "") for row in await cur.fetchall()]


async def has_unfinished_collection(jurisdiction_ocdid: str) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pipeline_runs WHERE jurisdiction_ocdid = %s AND finished_at IS NULL AND kind = %s)",
            (jurisdiction_ocdid, PipelineRunKind.GOVERNING_LAW_COLLECTOR),
        )
        row = await cur.fetchone()
    return bool(row and row[0])
