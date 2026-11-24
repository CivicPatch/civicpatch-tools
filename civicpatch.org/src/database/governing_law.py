from typing import LiteralString

from pydantic import BaseModel

from database.changeset_predicates import (
    NO_ATTEMPT_IN_FLIGHT,
    OLDEST_ATTEMPT_FIRST,
    attempts_join,
    due_after_days,
    settings_join,
)
from database.database import get_pool
from shared.schemas import GoverningLaw
from shared.utils.statuses import PipelineRunKind


class GoverningLawRow(BaseModel):
    """One active jurisdiction, with what it has: None until a collector run has written it."""

    jurisdiction_ocdid: str
    name: str
    # The place's own site from the registry; many places have none.
    url: str | None
    governing_law: GoverningLaw | None


async def get_governing_law_row(jurisdiction_ocdid: str) -> GoverningLawRow | None:
    """None for an unknown or inactive jurisdiction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, data->>'name', data->>'url', extras_governing_law
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
        url=row[2] or None,
        governing_law=GoverningLaw.model_validate(row[3]) if row[3] is not None else None,
    )


async def save_governing_law(cur, jurisdiction_ocdid: str, governing_law: GoverningLaw) -> None:
    await cur.execute(
        "UPDATE jurisdictions SET extras_governing_law = %s::jsonb WHERE jurisdiction_ocdid = %s",
        (governing_law.model_dump_json(), jurisdiction_ocdid),
    )


class CollectionCandidate(BaseModel):
    jurisdiction_ocdid: str
    name: str


async def get_collection_candidates(state: str, limit: int | None, state_batch_id: str | None) -> list[CollectionCandidate]:
    """Pipeline 1's: the state's places with no governing law yet, or one older than the cadence."""
    return await _candidates(
        PipelineRunKind.GOVERNING_LAW_COLLECTOR,
        f"""
        (j.extras_governing_law IS NULL
         OR (j.extras_governing_law->>'collected_at')::timestamptz
            < now() - make_interval(days => {due_after_days(PipelineRunKind.GOVERNING_LAW_COLLECTOR)}))
        """,
        {"state": state, "limit": limit, "state_batch_id": state_batch_id},
    )


async def get_organizations_collection_candidates(
    state: str, limit: int | None, state_batch_id: str | None
) -> list[CollectionCandidate]:
    """Pipeline 2's: the state's places with a governing law stored and no answer read from it yet. A
    pending pipeline 1 issue does not hold a place: pipeline 2 reads the law that was stored, and the
    issue waits for a person."""
    return await _candidates(
        PipelineRunKind.ORGANIZATIONS_COLLECTOR,
        """
        j.extras_governing_law->>'kind' IN ('charter', 'general_law')
        AND (j.extras_organizations IS NULL
             OR (j.extras_organizations->'extras'->>'governing_law_collected_at')::timestamptz
                < (j.extras_governing_law->>'collected_at')::timestamptz)
        """,
        {"state": state, "limit": limit, "state_batch_id": state_batch_id},
    )


async def _candidates(kind: PipelineRunKind, due: LiteralString, params: dict[str, object]) -> list[CollectionCandidate]:
    """Every pipeline's candidates read alike: active places below the state, none of this kind in flight
    or already tried in this batch (`state_batch_id`), then the pipeline's own `due` rule; least recently
    tried first."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT j.jurisdiction_ocdid, j.data->>'name' AS name
            FROM jurisdictions j
            {attempts_join(kind)}
            {settings_join(kind)}
            WHERE j.state = %(state)s AND j.status = 'active' AND j.level <> 'state'
              AND {NO_ATTEMPT_IN_FLIGHT}
              AND NOT EXISTS (
                  SELECT 1 FROM pipeline_runs tried
                  WHERE tried.jurisdiction_ocdid = j.jurisdiction_ocdid AND tried.kind = %(kind)s
                    AND tried.state_batch_id = %(state_batch_id)s
              )
              AND {due}
            ORDER BY {OLDEST_ATTEMPT_FIRST}
            LIMIT %(limit)s
            """,
            {**params, "kind": kind},
        )
        return [CollectionCandidate(jurisdiction_ocdid=row[0], name=row[1] or "") for row in await cur.fetchall()]
