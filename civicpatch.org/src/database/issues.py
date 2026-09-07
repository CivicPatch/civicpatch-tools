"""Issues, in two tables that mean different things.

`pipeline_run_issues` says a **run** went wrong — it errored, stopped at its spend cap, or came
back short. `changeset_issues` says a **person** reported something about a proposal they were
reviewing. Migration 186 split them; before it they shared one table whose `changeset_ids text[]`
held a changeset id, or a run id when the scrape died before minting one, as text with no foreign
key either way.

Both anchors are honest: every scrape changeset has a run, and a scrape that died before ingest
has a run and no changeset. So the run side never needs the changeset to name its jurisdiction —
`pipeline_runs.jurisdiction_ocdid` is a column — and reaches it in one indexed hop rather than a
cast and an array scan.

`run`, never `r`: `r` has meant `requests` (now `changesets`), `roles` and `pipeline_runs` in this
codebase, and these queries join two of the three.
"""

import json
from typing import Any

import shared.utils.id_utils
from database.changeset_predicates import WORK_IN_FLIGHT
from database.database import get_pool
from psycopg import sql
from shared.utils.statuses import PipelineIssueStatus, PipelineIssueType


# An issue blocks only while the changeset its run produced is still open — otherwise it froze
# the jurisdiction against the very scrape that would have resolved it.
# `LEFT JOIN`: a run that died before ingest has no changeset, so it blocks nothing.
_BLOCKING_JURISDICTIONS = f"""
    SELECT DISTINCT run.jurisdiction_ocdid
    FROM pipeline_run_issues issue
    JOIN pipeline_runs run ON run.id = issue.pipeline_run_id
    LEFT JOIN changesets ON changesets.id = run.changeset_id
    WHERE issue.status = %s
      AND {WORK_IN_FLIGHT}
"""


async def jurisdiction_ocdids_with_pending_issues() -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(_BLOCKING_JURISDICTIONS, (PipelineIssueStatus.PENDING,))
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def jurisdiction_ocdids_with_pending_issues_in_state(state_code: str) -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            _BLOCKING_JURISDICTIONS + " AND run.jurisdiction_ocdid LIKE %s",
            (PipelineIssueStatus.PENDING, f"%state:{state_code}%"),
        )
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def has_pending_issues(changeset_id: str) -> bool:
    """Gates auto-publish: the roster-derived summary never reads this table, so a capped run
    used to publish its partial roster regardless."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT 1 FROM pipeline_run_issues issue
            JOIN pipeline_runs run ON run.id = issue.pipeline_run_id
            WHERE issue.status = %s AND run.changeset_id = %s
            LIMIT 1
            """,
            (PipelineIssueStatus.PENDING, changeset_id),
        )
        return await cur.fetchone() is not None


# ── Writing them ─────────────────────────────────────────────────────────────


async def upsert_issue(pipeline_run_id: str, issue_type: str, issues: list[dict]) -> None:
    """Keyed on the run, so a retry refreshes and a later run files its own row."""
    if not issues:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO pipeline_run_issues (pipeline_run_id, issue_type, data, status)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (pipeline_run_id, issue_type) DO UPDATE SET
              data = EXCLUDED.data,
              -- Re-reported, so open again whatever it was.
              status = 'pending',
              resolved_at = NULL
            """,
            [
                (
                    pipeline_run_id,
                    issue_type,
                    json.dumps(issue),
                    PipelineIssueStatus.PENDING,
                )
                for issue in issues
            ],
        )


async def resolve_issue(issue_id: str) -> None:
    """An id belongs to exactly one table, so both statements run and one matches."""
    pool = await get_pool()
    async with pool.connection() as conn:
        for table in ("pipeline_run_issues", "changeset_issues"):
            await conn.execute(
                sql.SQL("UPDATE {} SET status = %s, resolved_at = NOW() WHERE id = %s").format(
                    sql.Identifier(table)
                ),
                (PipelineIssueStatus.RESOLVED, issue_id),
            )


async def resolve_issues(issue_ids: list[str]) -> int:
    """Two statements for a page. Returns rows actually moved, so an already-settled id shows."""
    if not issue_ids:
        return 0
    pool = await get_pool()
    resolved = 0
    async with pool.connection() as conn, conn.cursor() as cur:
        for table in ("pipeline_run_issues", "changeset_issues"):
            await cur.execute(
                sql.SQL(
                    "UPDATE {} SET status = %s, resolved_at = NOW() "
                    "WHERE id = ANY(%s::uuid[]) AND status = %s"
                ).format(sql.Identifier(table)),
                (PipelineIssueStatus.RESOLVED, issue_ids, PipelineIssueStatus.PENDING),
            )
            resolved += cur.rowcount
    return resolved


async def set_issue_flagged(issue_id: str, is_flagged: bool) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        for table in ("pipeline_run_issues", "changeset_issues"):
            await conn.execute(
                sql.SQL("UPDATE {} SET is_flagged = %s WHERE id = %s").format(
                    sql.Identifier(table)
                ),
                (is_flagged, issue_id),
            )


async def supersede_prior_jurisdiction_issues(
    jurisdiction_ocdid: str, current_changeset_id: str
) -> None:
    """A newer run for this jurisdiction settles what older ones reported."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pipeline_run_issues
            SET status = %s, resolved_at = NOW()
            WHERE status = %s
              AND pipeline_run_id IN (
                SELECT run.id FROM pipeline_runs run
                WHERE run.jurisdiction_ocdid = %s
                  AND (run.changeset_id IS NULL OR run.changeset_id::text <> %s)
              )
            """,
            (
                PipelineIssueStatus.SUPERSEDED,
                PipelineIssueStatus.PENDING,
                jurisdiction_ocdid,
                current_changeset_id,
            ),
        )


# ── What a reviewer reported ─────────────────────────────────────────────────


async def create_user_reported_issue(
    changeset_id: str,
    title: str,
    body: str,
    github_issue_url: str,
    github_issue_number: int,
    reported_by_user_id: str,
) -> str:
    """No uniqueness here: two reports about one roster are two reports."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO changeset_issues (changeset_id, issue_type, data, status)
            VALUES (%s, %s, %s, %s)
            RETURNING id::text
            """,
            (
                changeset_id,
                PipelineIssueType.USER_REPORTED,
                json.dumps(
                    {
                        "title": title,
                        "body": body,
                        "github_issue_url": github_issue_url,
                        "github_issue_number": github_issue_number,
                        "reported_by_user_id": reported_by_user_id,
                    }
                ),
                PipelineIssueStatus.PENDING,
            ),
        )
        row = await cur.fetchone()
    assert row, "create_user_reported_issue RETURNING returned no row"
    return row[0]


async def get_user_reported_issues_for_changeset(changeset_id: str) -> list[dict]:
    """Reviewer-filed issues for this changeset only — pipeline issues are browsed separately,
    on the admin issues page."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, data, status, created_at
            FROM changeset_issues
            WHERE issue_type = %s AND changeset_id = %s
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


# ── The two listings ─────────────────────────────────────────────────────────
#
# Two queries, not one union over both tables. They are different pages: a pipeline issue is
# read by whoever runs the scrapes, a reported one by whoever reviews rosters. Sharing a query
# meant a `kind` discriminator, doubled parameters, and a filter that had to name only columns
# both selects happened to expose.
