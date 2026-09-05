import json
import uuid
from typing import Any

import shared.utils.id_utils
from database.changeset_predicates import WORK_IN_FLIGHT
from database.database import get_pool
from psycopg import sql
from shared.utils.statuses import PipelineIssueStatus, PipelineIssueType


def _build_jurisdictions(
    ocdids: list[str] | None, name_by_ocdid: dict[str, str] | None = None
) -> list[dict]:
    result = []
    for ocdid in ocdids or []:
        try:
            folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(ocdid)
            parts = folder.split("/")
            result.append(
                {
                    "jurisdiction_ocdid": ocdid,
                    "folder": folder,
                    "path": folder,
                    "name": (name_by_ocdid or {}).get(ocdid) or ocdid,
                    "state": parts[0] if parts else "",
                    "locality": parts[2] if len(parts) > 2 else "",
                }
            )
        except Exception:
            pass
    return result


# An issue only blocks its jurisdiction while the changeset it hangs off is still open.
#
# Without `WORK_IN_FLIGHT` a pending issue on an already published-or-dismissed changeset froze
# its jurisdiction forever: nothing could re-scrape it, so no new run could finish, so
# `supersede_prior_jurisdiction_issues` — which only fires from `finalize_pipeline_run` — never
# cleared the issue. The issue blocked the scrape whose completion would have resolved it.
# Measured 2026-09-05: all 15 pending issues in dev sat on terminal changesets, freezing 10
# jurisdictions.
#
# Both readers narrow together on purpose. `jurisdiction_ocdids_with_pending_issues` gates scrape candidates
# and the by-state one feeds the coverage page's `blocked` count, which means "blocked from
# scraping" — if they disagreed the page would report a block that no longer exists.
async def jurisdiction_ocdids_with_pending_issues() -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT DISTINCT changesets.jurisdiction_ocdid
            FROM issues pi
            JOIN changesets ON changesets.id::text = ANY(pi.changeset_ids)
            WHERE pi.status = %s
              AND changesets.jurisdiction_ocdid IS NOT NULL
              AND {WORK_IN_FLIGHT}
            """,
            (PipelineIssueStatus.PENDING,),
        )
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def jurisdiction_ocdids_with_pending_issues_in_state(state_code: str) -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT DISTINCT changesets.jurisdiction_ocdid
            FROM issues pi
            JOIN changesets ON changesets.id::text = ANY(pi.changeset_ids)
            WHERE pi.status = %s
              AND changesets.jurisdiction_ocdid LIKE %s
              AND {WORK_IN_FLIGHT}
            """,
            (
                PipelineIssueStatus.PENDING,
                f"%state:{state_code}%",
            ),
        )
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def resolve_issue(issue_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE issues SET status = %s, resolved_at = NOW() WHERE id = %s",
            (PipelineIssueStatus.RESOLVED, issue_id),
        )


async def supersede_prior_jurisdiction_issues(
    jurisdiction_ocdid: str, current_changeset_id: str
) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE issues
            SET status = %s, resolved_at = NOW()
            WHERE status = %s
              AND NOT (%s = ANY(changeset_ids))
              AND EXISTS (
                SELECT 1 FROM changesets
                WHERE changesets.id::text = ANY(issues.changeset_ids)
                  AND changesets.jurisdiction_ocdid = %s
              )
            """,
            (
                PipelineIssueStatus.SUPERSEDED,
                PipelineIssueStatus.PENDING,
                current_changeset_id,
                jurisdiction_ocdid,
            ),
        )


async def upsert_issue(changeset_id: str, issue_type: str, issues: list[dict]) -> None:
    if not issues:
        return
    # `issue_key` is the subject's own id. `unrecognized_role` was the one type that keyed on
    # something else — the role — and accumulated changesets; migration 179 drained it, so a
    # conflict now always means the same subject raising the same issue again.
    rows = [
        (
            issue_type,
            changeset_id,
            [changeset_id],
            json.dumps(issue),
            PipelineIssueStatus.PENDING,
        )
        for issue in issues
    ]

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO issues (issue_type, issue_key, changeset_ids, data, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (issue_type, issue_key) DO UPDATE SET
              changeset_ids = (
                SELECT array_agg(DISTINCT r)
                FROM unnest(issues.changeset_ids || EXCLUDED.changeset_ids) r
              ),
              data = issues.data,
              -- Re-reported, so it is open again whatever it was. The CASE this replaces
              -- had one live branch, `pr_opened`, which migration 174 retired.
              status = 'pending',
              resolved_at = NULL
            """,
            rows,
        )


async def create_user_reported_issue(
    changeset_id: str,
    title: str,
    body: str,
    github_issue_url: str,
    github_issue_number: int,
    reported_by_user_id: str,
) -> str:
    data = json.dumps(
        {
            "title": title,
            "body": body,
            "github_issue_url": github_issue_url,
            "github_issue_number": github_issue_number,
            "reported_by_user_id": reported_by_user_id,
        }
    )
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO issues (issue_type, issue_key, changeset_ids, data, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            (
                PipelineIssueType.USER_REPORTED,
                str(uuid.uuid4()),
                [changeset_id],
                data,
                PipelineIssueStatus.PENDING,
            ),
        )
        row = await cur.fetchone()
    assert row, "create_user_reported_issue RETURNING returned no row"
    return row[0]


async def get_user_reported_issues_for_request(changeset_id: str) -> list[dict]:
    """Reviewer-filed GitHub issues for this request only — not pipeline-internal
    issue types (those are browsed separately, via the admin issues page)."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, data, status, created_at
            FROM issues
            WHERE issue_type = %s AND %s = ANY(changeset_ids)
            ORDER BY created_at DESC
            """,
            (PipelineIssueType.USER_REPORTED, changeset_id),
        )
        rows = await cur.fetchall()
    return [
        {
            "id": row[0],
            "title": row[1].get("title"),
            "github_issue_url": row[1].get("github_issue_url"),
            "github_issue_number": row[1].get("github_issue_number"),
            "status": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
        }
        for row in rows
    ]


async def get_issues_page(
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
        active_statuses = [PipelineIssueStatus.PENDING]
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
        conditions.append(
            sql.SQL(
                "EXISTS (SELECT 1 FROM changesets WHERE changesets.id::text = ANY(ri.changeset_ids) AND changesets.jurisdiction_ocdid LIKE %s)"
            )
        )
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
                       array_agg(DISTINCT changesets.jurisdiction_ocdid)
                           FILTER (WHERE changesets.jurisdiction_ocdid IS NOT NULL) AS ocdids
                FROM issues ri
                LEFT JOIN changesets ON changesets.id::text = ANY(ri.changeset_ids)
                GROUP BY ri.id
            )
            SELECT ri.id::text, ri.issue_type, ri.issue_key, ri.changeset_ids,
                   ri.data, ri.status, ri.resolved_at, ri.created_at,
                   COALESCE(ij.ocdids, ARRAY[]::text[]) AS raw_jurisdiction_ocdids,
                   COUNT(*) OVER() AS total_count,
                   (
                       SELECT jsonb_object_agg(u.ocdid, COALESCE(j.data->>'name', u.ocdid))
                       FROM unnest(COALESCE(ij.ocdids, ARRAY[]::text[])) AS u(ocdid)
                       LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = u.ocdid
                   ) AS jurisdiction_names,
                   ri.is_flagged
            FROM issues ri
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
        jurisdictions = _build_jurisdictions(r[8], name_by_ocdid=r[10])
        result.append(
            {
                "id": r[0],
                "issue_type": r[1],
                "issue_key": r[2],
                "changeset_ids": r[3],
                "data": r[4],
                "status": r[5],
                "resolved_at": r[6].isoformat() if r[6] else None,
                "created_at": r[7].isoformat() if r[7] else None,
                "is_flagged": r[11],
                "states": sorted({j["state"] for j in jurisdictions if j["state"]}),
                "jurisdictions": jurisdictions,
            }
        )
    return result, total


async def get_issue_counts(state_code: str | None = None) -> dict[str, int]:
    pool = await get_pool()
    active_statuses = [PipelineIssueStatus.PENDING]
    params: list[Any] = list(active_statuses)
    state_filter = sql.SQL("")
    if state_code:
        state_filter = sql.SQL(
            "AND EXISTS (SELECT 1 FROM changesets WHERE changesets.id::text = ANY(pi.changeset_ids) AND changesets.jurisdiction_ocdid LIKE %s)"
        )
        params.append(f"%state:{state_code.lower()}%")
    query = sql.SQL("""
        SELECT pi.issue_type, COUNT(*) AS cnt
        FROM issues pi
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


async def set_issue_flagged(issue_id: str, is_flagged: bool) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE issues SET is_flagged = %s WHERE id = %s",
            (is_flagged, issue_id),
        )


async def get_issue_by_id(issue_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, issue_type, issue_key, changeset_ids, data, status, resolved_at, created_at
            FROM issues WHERE id = %s
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
        "changeset_ids": row[3],
        "data": row[4],
        "status": row[5],
        "resolved_at": row[6].isoformat() if row[6] else None,
        "created_at": row[7].isoformat() if row[7] else None,
    }
