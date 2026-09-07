"""What the issues page reads: the two listings, their counts, and one issue by id.

`issues.py` owns the other half — filing, settling, and whether an issue blocks a scrape.
"""

from typing import Any

import shared.utils.id_utils
from database.database import get_pool
from psycopg import sql
from shared.utils.statuses import PipelineIssueStatus, PipelineIssueType


def _jurisdiction_entry(ocdid: str | None, name: str | None) -> list[dict]:
    """A list of one: an issue has exactly one subject, so one jurisdiction."""
    if not ocdid:
        return []
    try:
        state = shared.utils.id_utils.parse_jurisdiction_ocdid(ocdid).state
    except ValueError:
        return []
    return [{"jurisdiction_ocdid": ocdid, "name": name or ocdid, "state": state}]


_RUN_JURISDICTION = sql.SQL("run.jurisdiction_ocdid")
_CHANGESET_JURISDICTION = sql.SQL("changesets.jurisdiction_ocdid")


def _listing_filters(
    issue_types: list[str],
    state_code: str | None,
    show_archived: bool,
    jurisdiction_column: sql.Composable,
) -> tuple[sql.Composable, list[Any]]:
    """The caller names its jurisdiction column: bare, it is ambiguous against the
    `jurisdictions` join the listings carry."""
    statuses = (
        [PipelineIssueStatus.RESOLVED, PipelineIssueStatus.SUPERSEDED]
        if show_archived
        else [PipelineIssueStatus.PENDING]
    )
    conditions: list[sql.Composable] = [
        sql.SQL("issue.status IN ({})").format(
            sql.SQL(", ").join(sql.Placeholder() for _ in statuses)
        )
    ]
    params: list[Any] = list(statuses)
    if issue_types:
        conditions.append(
            sql.SQL("issue.issue_type IN ({})").format(
                sql.SQL(", ").join(sql.Placeholder() for _ in issue_types)
            )
        )
        params.extend(issue_types)
    if state_code:
        conditions.append(sql.SQL("{} LIKE %s").format(jurisdiction_column))
        params.append(f"%state:{state_code.lower()}%")
    return sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions), params


def _row(record, jurisdiction_name: str | None) -> dict:
    jurisdictions = _jurisdiction_entry(record[7], jurisdiction_name)
    return {
        "id": record[0],
        "issue_type": record[1],
        "data": record[2],
        "status": record[3],
        "resolved_at": record[4].isoformat() if record[4] else None,
        "created_at": record[5].isoformat() if record[5] else None,
        "is_flagged": record[6],
        "states": sorted({j["state"] for j in jurisdictions if j["state"]}),
        "jurisdictions": jurisdictions,
    }


_ISSUE_COLUMNS = """
    issue.id::text, issue.issue_type, issue.data, issue.status,
    issue.resolved_at, issue.created_at, issue.is_flagged
"""


async def get_pipeline_run_issues_page(
    issue_types: list[str],
    page: int,
    per_page: int,
    sort_desc: bool = True,
    state_code: str | None = None,
    show_archived: bool = False,
) -> tuple[list[dict], int]:
    """What the scrapes reported. Keyed on the run's own jurisdiction, so a run that died
    before ingest still appears."""
    where, params = _listing_filters(
        issue_types, state_code, show_archived, _RUN_JURISDICTION
    )
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT {columns}, run.jurisdiction_ocdid, run.changeset_id::text,
                   issue.pipeline_run_id::text,
                   COALESCE(j.data->>'name', run.jurisdiction_ocdid),
                   COUNT(*) OVER() AS total_count
            FROM pipeline_run_issues issue
            JOIN pipeline_runs run ON run.id = issue.pipeline_run_id
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = run.jurisdiction_ocdid
            {where}
            ORDER BY issue.created_at {order}
            LIMIT %s OFFSET %s
            """).format(
                columns=sql.SQL(_ISSUE_COLUMNS),
                where=where,
                order=sql.SQL("DESC") if sort_desc else sql.SQL("ASC"),
            ),
            params + [per_page, (page - 1) * per_page],
        )
        rows = await cur.fetchall()
    total = rows[0][11] if rows else 0
    return [
        {
            **_row(row, row[10]),
            "changeset_id": row[8],
            "pipeline_run_id": row[9],
        }
        for row in rows
    ], total


async def get_changeset_issues_page(
    issue_types: list[str],
    page: int,
    per_page: int,
    sort_desc: bool = True,
    state_code: str | None = None,
    show_archived: bool = False,
) -> tuple[list[dict], int]:
    """What people reported while reviewing."""
    where, params = _listing_filters(
        issue_types, state_code, show_archived, _CHANGESET_JURISDICTION
    )
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT {columns}, changesets.jurisdiction_ocdid, changesets.id::text,
                   COALESCE(j.data->>'name', changesets.jurisdiction_ocdid),
                   COUNT(*) OVER() AS total_count
            FROM changeset_issues issue
            JOIN changesets ON changesets.id = issue.changeset_id
            LEFT JOIN jurisdictions j
                   ON j.jurisdiction_ocdid = changesets.jurisdiction_ocdid
            {where}
            ORDER BY issue.created_at {order}
            LIMIT %s OFFSET %s
            """).format(
                columns=sql.SQL(_ISSUE_COLUMNS),
                where=where,
                order=sql.SQL("DESC") if sort_desc else sql.SQL("ASC"),
            ),
            params + [per_page, (page - 1) * per_page],
        )
        rows = await cur.fetchall()
    total = rows[0][10] if rows else 0
    return [{**_row(row, row[9]), "changeset_id": row[8]} for row in rows], total


async def get_pipeline_run_issue_counts(state_code: str | None = None) -> dict[str, int]:
    where, params = _listing_filters([], state_code, False, _RUN_JURISDICTION)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT issue.issue_type, COUNT(*)::int
            FROM pipeline_run_issues issue
            JOIN pipeline_runs run ON run.id = issue.pipeline_run_id
            {where}
            GROUP BY issue.issue_type
            """).format(where=where),
            params,
        )
        return {row[0]: row[1] for row in await cur.fetchall()}


async def get_changeset_issue_counts(state_code: str | None = None) -> dict[str, int]:
    where, params = _listing_filters([], state_code, False, _CHANGESET_JURISDICTION)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT issue.issue_type, COUNT(*)::int
            FROM changeset_issues issue
            JOIN changesets ON changesets.id = issue.changeset_id
            {where}
            GROUP BY issue.issue_type
            """).format(where=where),
            params,
        )
        return {row[0]: row[1] for row in await cur.fetchall()}


async def get_issue_by_id(issue_id: str) -> dict | None:
    """Probes both: a caller holding an id does not know which page it came from."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT {columns}, run.jurisdiction_ocdid, run.changeset_id::text,
                   issue.pipeline_run_id::text
            FROM pipeline_run_issues issue
            JOIN pipeline_runs run ON run.id = issue.pipeline_run_id
            WHERE issue.id = %s
            """).format(columns=sql.SQL(_ISSUE_COLUMNS)),
            (issue_id,),
        )
        row = await cur.fetchone()
        if row:
            return {**_row(row, None), "changeset_id": row[8], "pipeline_run_id": row[9]}

        await cur.execute(
            sql.SQL("""
            SELECT {columns}, changesets.jurisdiction_ocdid, changesets.id::text
            FROM changeset_issues issue
            JOIN changesets ON changesets.id = issue.changeset_id
            WHERE issue.id = %s
            """).format(columns=sql.SQL(_ISSUE_COLUMNS)),
            (issue_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {**_row(row, None), "changeset_id": row[8], "pipeline_run_id": None}


# Keyed on the run, so the state comes straight off it rather than through the changeset — which
# a capped run may not even have. Windowed to the calendar month because that is the window the
# cap it refers to is measured over: "hit twice" means twice this month, not twice ever.
COST_CAP_HITS_SQL = """
SELECT count(*)::int
FROM pipeline_run_issues issue
JOIN pipeline_runs run ON run.id = issue.pipeline_run_id
JOIN jurisdictions j ON j.jurisdiction_ocdid = run.jurisdiction_ocdid
WHERE issue.issue_type = %(issue_type)s
  AND j.state = %(state)s
  AND issue.created_at >= date_trunc('month', now() AT TIME ZONE 'utc')
"""


async def count_cost_cap_hits_this_month(state: str) -> int:
    """One truncated run is noise; a third of them means the cap is below what the state
    costs."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            COST_CAP_HITS_SQL,
            {"issue_type": PipelineIssueType.COST_CAP_REACHED, "state": state},
        )
        row = await cur.fetchone()
    assert row, "count(*) always returns a row"
    return row[0]
