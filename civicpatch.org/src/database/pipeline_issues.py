import json
from typing import Any

from psycopg import sql

import shared.utils.id_utils
from database.database import get_pool
from shared.utils.statuses import PipelineIssueCategory, PipelineIssueStatus, PipelineIssueType


def _build_jurisdictions(ocdids: list[str] | None, name_by_ocdid: dict[str, str] | None = None) -> list[dict]:
    result = []
    for ocdid in (ocdids or []):
        try:
            folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(ocdid)
            parts = folder.split("/")
            result.append({
                "jurisdiction_ocdid": ocdid,
                "folder": folder,
                "path": folder,
                "name": (name_by_ocdid or {}).get(ocdid) or ocdid,
                "state": parts[0] if parts else "",
                "locality": parts[2] if len(parts) > 2 else "",
            })
        except Exception:
            pass
    return result


async def get_pending_error_issue_ocdids() -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT r.jurisdiction_ocdid
            FROM pipeline_issues pi
            JOIN requests r ON r.id::text = ANY(pi.request_ids)
            WHERE pi.category = %s
              AND pi.status IN (%s, %s)
              AND r.jurisdiction_ocdid IS NOT NULL
            """,
            (PipelineIssueCategory.ERROR, PipelineIssueStatus.PENDING, PipelineIssueStatus.PR_OPENED),
        )
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def get_unrecognized_roles_grouped() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT issue_key AS role,
                   request_ids,
                   data->'person_names' AS person_names,
                   array_length(request_ids, 1) AS occurrence_count
            FROM pipeline_issues
            WHERE issue_type = 'unrecognized_role'
              AND status = 'pending'
            ORDER BY array_length(request_ids, 1) DESC
            """
        )
        rows = await cur.fetchall()
    return [
        {
            "role": r[0],
            "request_ids": r[1],
            "person_names": r[2] or [],
            "occurrence_count": r[3],
        }
        for r in rows
    ]


async def resolve_unrecognized_role_group(request_ids: list[str]) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE review_session_entries
            SET status = 'resolved', resolved_at = NOW()
            WHERE request_ids && %s::text[]
              AND status != 'resolved'
            """,
            (request_ids,),
        )


async def resolve_pipeline_issue(issue_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE pipeline_issues SET status = %s, resolved_at = NOW() WHERE id = %s",
            (PipelineIssueStatus.RESOLVED, issue_id),
        )


async def open_pipeline_issue_pull_request(issue_id: str, pull_request_url: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE pipeline_issues SET status = %s, pull_request_url = %s WHERE id = %s",
            (PipelineIssueStatus.PR_OPENED, pull_request_url, issue_id),
        )


async def get_pipeline_issue_by_pull_request_url(pull_request_url: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, status FROM pipeline_issues WHERE pull_request_url = %s",
            (pull_request_url,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {"id": row[0], "status": row[1]}


async def get_pipeline_issues_with_open_pr() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, pull_request_url FROM pipeline_issues WHERE status = %s",
            (PipelineIssueStatus.PR_OPENED,),
        )
        rows = await cur.fetchall()
    return [{"id": r[0], "pull_request_url": r[1]} for r in rows]


async def reopen_pipeline_issue(issue_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE pipeline_issues SET status = %s, pull_request_url = NULL WHERE id = %s",
            (PipelineIssueStatus.PENDING, issue_id),
        )


async def supersede_prior_jurisdiction_issues(jurisdiction_ocdid: str, current_request_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pipeline_issues
            SET status = %s, resolved_at = NOW()
            WHERE status = %s
              AND NOT (%s = ANY(request_ids))
              AND EXISTS (
                SELECT 1 FROM requests r
                WHERE r.id::text = ANY(pipeline_issues.request_ids)
                  AND r.jurisdiction_ocdid = %s
              )
            """,
            (
                PipelineIssueStatus.SUPERSEDED,
                PipelineIssueStatus.PENDING,
                current_request_id,
                jurisdiction_ocdid,
            ),
        )


async def upsert_pipeline_issue(request_id: str, issue_type: str, category: str, issues: list[dict]) -> None:
    if not issues:
        return
    rows = []
    for issue in issues:
        if issue_type == PipelineIssueType.UNRECOGNIZED_ROLE:
            issue_key = issue["role"]
            data = json.dumps({"person_names": [issue.get("person_name", "")]})
        else:
            issue_key = request_id
            data = json.dumps(issue)
        rows.append((issue_type, issue_key, category, [request_id], data, PipelineIssueStatus.PENDING))

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO pipeline_issues (issue_type, issue_key, category, request_ids, data, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (issue_type, issue_key) DO UPDATE SET
              request_ids = (
                SELECT array_agg(DISTINCT r)
                FROM unnest(pipeline_issues.request_ids || EXCLUDED.request_ids) r
              ),
              data = CASE
                WHEN pipeline_issues.issue_type = 'unrecognized_role' THEN
                  jsonb_set(
                    pipeline_issues.data,
                    '{person_names}',
                    (SELECT jsonb_agg(DISTINCT v)
                     FROM jsonb_array_elements_text(
                       COALESCE(pipeline_issues.data->'person_names', '[]'::jsonb) ||
                       COALESCE(EXCLUDED.data->'person_names', '[]'::jsonb)
                     ) v)
                  )
                ELSE pipeline_issues.data
              END,
              status = CASE
                WHEN pipeline_issues.status IN ('resolved', 'superseded') THEN 'pending'
                ELSE pipeline_issues.status
              END,
              resolved_at = CASE
                WHEN pipeline_issues.status IN ('resolved', 'superseded') THEN NULL
                ELSE pipeline_issues.resolved_at
              END
            """,
            rows,
        )


async def get_pipeline_issues_page(
    issue_types: list[str],
    page: int,
    per_page: int,
    sort_desc: bool = True,
    state_code: str | None = None,
    show_archived: bool = False,
) -> tuple[list[dict], int]:
    if show_archived:
        active_statuses = [PipelineIssueStatus.RESOLVED, PipelineIssueStatus.SUPERSEDED]
    else:
        active_statuses = [PipelineIssueStatus.PENDING, PipelineIssueStatus.PR_OPENED]
    conditions: list[sql.Composable] = [
        sql.SQL("ri.status IN ({})").format(
            sql.SQL(", ").join(sql.Placeholder() for _ in range(len(active_statuses)))
        )
    ]
    params: list[Any] = list(active_statuses)
    if issue_types:
        conditions.append(
            sql.SQL("ri.issue_type IN ({})").format(
                sql.SQL(", ").join(sql.Placeholder() for _ in range(len(issue_types)))
            )
        )
        params.extend(issue_types)
    if state_code:
        conditions.append(sql.SQL(
            "EXISTS (SELECT 1 FROM requests r WHERE r.id::text = ANY(ri.request_ids) AND r.jurisdiction_ocdid LIKE %s)"
        ))
        params.append(f"%state:{state_code.lower()}%")
    where_clause = sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions)
    order_clause = sql.SQL("DESC") if sort_desc else sql.SQL("ASC")
    offset = (page - 1) * per_page
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            WITH issue_jurisdictions AS (
                SELECT ri.id AS issue_id,
                       array_agg(DISTINCT r.jurisdiction_ocdid)
                           FILTER (WHERE r.jurisdiction_ocdid IS NOT NULL) AS ocdids
                FROM pipeline_issues ri
                LEFT JOIN requests r ON r.id::text = ANY(ri.request_ids)
                GROUP BY ri.id
            )
            SELECT ri.id::text, ri.issue_type, ri.issue_key, ri.request_ids,
                   ri.data, ri.status, ri.resolved_at, ri.created_at,
                   COALESCE(ij.ocdids, ARRAY[]::text[]) AS raw_jurisdiction_ocdids,
                   COUNT(*) OVER() AS total_count,
                   ri.pull_request_url,
                   (
                       SELECT jsonb_object_agg(u.ocdid, COALESCE(j.data->>'name', u.ocdid))
                       FROM unnest(COALESCE(ij.ocdids, ARRAY[]::text[])) AS u(ocdid)
                       LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = u.ocdid
                   ) AS jurisdiction_names,
                   ri.category,
                   ri.is_flagged
            FROM pipeline_issues ri
            LEFT JOIN issue_jurisdictions ij ON ij.issue_id = ri.id
            {where}
            ORDER BY ri.created_at {order}
            LIMIT %s OFFSET %s
            """).format(where=where_clause, order=order_clause),
            params + [per_page, offset],
        )
        rows = await cur.fetchall()
    total = rows[0][9] if rows else 0
    result = []
    for r in rows:
        jurisdictions = _build_jurisdictions(r[8], name_by_ocdid=r[11])
        result.append({
            "id": r[0],
            "issue_type": r[1],
            "issue_key": r[2],
            "request_ids": r[3],
            "data": r[4],
            "status": r[5],
            "resolved_at": r[6].isoformat() if r[6] else None,
            "created_at": r[7].isoformat() if r[7] else None,
            "pull_request_url": r[10],
            "category": r[12],
            "is_flagged": r[13],
            "states": sorted({j["state"] for j in jurisdictions if j["state"]}),
            "jurisdictions": jurisdictions,
        })
    return result, total


async def get_pipeline_issue_counts(state_code: str | None = None) -> dict[str, int]:
    pool = await get_pool()
    active_statuses = [PipelineIssueStatus.PENDING, PipelineIssueStatus.PR_OPENED]
    params: list[Any] = list(active_statuses)
    state_filter = sql.SQL("")
    if state_code:
        state_filter = sql.SQL(
            "AND EXISTS (SELECT 1 FROM requests r WHERE r.id::text = ANY(pi.request_ids) AND r.jurisdiction_ocdid LIKE %s)"
        )
        params.append(f"%state:{state_code.lower()}%")
    query = sql.SQL("""
        SELECT pi.issue_type, COUNT(*) AS cnt
        FROM pipeline_issues pi
        WHERE pi.status IN ({statuses})
        {state_filter}
        GROUP BY pi.issue_type
    """).format(
        statuses=sql.SQL(", ").join(sql.Placeholder() for _ in active_statuses),
        state_filter=state_filter,
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, params)
        rows = await cur.fetchall()
    return {row[0]: row[1] for row in rows}


async def set_pipeline_issue_flagged(issue_id: str, is_flagged: bool) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE pipeline_issues SET is_flagged = %s WHERE id = %s",
            (is_flagged, issue_id),
        )


async def get_pipeline_issue_by_id(issue_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, issue_type, issue_key, request_ids, data, status, resolved_at, created_at
            FROM pipeline_issues WHERE id = %s
            """,
            (issue_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "issue_type": row[1],
        "issue_key": row[2],
        "request_ids": row[3],
        "data": row[4],
        "status": row[5],
        "resolved_at": row[6].isoformat() if row[6] else None,
        "created_at": row[7].isoformat() if row[7] else None,
    }
