"""Which changesets are available for review, and the reads the review pool needs.

Named for the pool rather than for `pull_requests`, the table it used to query and which
migration 141 dropped. `review_priority` is the other half: this decides membership,
`AVAILABLE_FOR_REVIEW`, and that one decides ordering.
"""

from typing import List, Optional

from psycopg import sql
from shared.utils.statuses import (
    ChangesetKind,
)
from database.database import get_pool, to_iso
from database.changeset_predicates import AVAILABLE_FOR_REVIEW, WORK_IN_FLIGHT
from database.review_priority import issue_count, issue_priority



async def list_open_changesets(
    state_code: Optional[str] = None,
    jurisdiction_ocdid: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[List[dict], int, int]:
    conditions: list[sql.Composable] = [sql.SQL(AVAILABLE_FOR_REVIEW)]
    params: list = []

    if jurisdiction_ocdid:
        conditions.append(sql.SQL("changesets.jurisdiction_ocdid = %s"))
        params.append(jurisdiction_ocdid)
    elif state_code:
        conditions.append(sql.SQL("changesets.jurisdiction_ocdid LIKE %s"))
        params.append(f"%state:{state_code}%")

    where = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(conditions))
    offset = (page - 1) * per_page

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE {count} > 0)
            FROM changesets
            {}
            """).format(
                where,
                count=sql.SQL(issue_count("changesets.jurisdiction_ocdid")),
            ),
            params,
        )
        count_row = await cur.fetchone()
        total, with_issues = count_row if count_row is not None else (0, 0)

        await cur.execute(
            sql.SQL("""
            SELECT changesets.id::text, changesets.change_url, {status},
                   changesets.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   changesets.created_at,
                   {count} AS issue_count
            FROM changesets
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = changesets.jurisdiction_ocdid
            {}
            -- `changesets.id` breaks ties so paging is stable: without a total order a row can appear
            -- on two pages or none. Same reason `_SEARCH_ORDER` ends on jurisdiction_ocdid —
            -- and cards created in one batch share a `created_at` to the microsecond.
            ORDER BY {priority} DESC, changesets.created_at DESC, changesets.id
            LIMIT %s OFFSET %s
            """).format(where, status=sql.SQL('changesets.changeset_state'),
                        count=sql.SQL(issue_count("changesets.jurisdiction_ocdid")),
                        priority=sql.SQL(issue_priority("changesets.jurisdiction_ocdid"))),
            params + [per_page, offset],
        )
        rows = await cur.fetchall()

    results = [
        {
            "changeset_id": r[0],
            "created_at": to_iso(r[5]),
            "issue_count": r[6],
            "jurisdiction": {"ocdid": r[3], "name": r[4], "path": r[3]},
            "pr": {"url": r[1], "status": r[2]},
        }
        for r in rows
    ]
    return results, total, with_issues


async def get_changeset_for_review(changeset_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT changesets.change_url, changesets.changeset_state,
                   changesets.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   jur.data->>'url' AS jurisdiction_website_url
            FROM changesets
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = changesets.jurisdiction_ocdid
            WHERE changesets.id = %s AND changesets.kind != %s
            """,
            (changeset_id, ChangesetKind.JURISDICTION_EDIT),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "changeset_id": changeset_id,
            "jurisdiction": {
                "ocdid": row[2],
                "name": row[3],
                "path": row[2],
                "website_url": row[4],
            },
            # `number` no longer identifies anything — publishing is keyed on the request.
            "pr": {
                "url": row[0],
                "status": row[1],
            },
        }



async def get_changeset_data(changeset_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT changesets.id::text, changesets.change_url, changesets.changeset_state,
                   changesets.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   jur.data->>'url' AS jurisdiction_website_url
            FROM changesets
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = changesets.jurisdiction_ocdid
            WHERE changesets.id::text = %s AND changesets.kind != %s
            """,
            (changeset_id, ChangesetKind.JURISDICTION_EDIT),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "changeset_id": row[0],
            "jurisdiction_ocdid": row[3],
            "jurisdiction_name": row[4],
            "jurisdiction_website_url": row[5],
            "pr": {"url": row[1], "status": row[2]},
        }


# These two answer "is there already work in flight for this jurisdiction?" — they gate
# starting a duplicate scrape, choosing the next scrape candidate, and the coverage figure.
# They asked GitHub because an open pull request used to BE that state. Nothing opens one now,
# so the question is a plain test on the changeset: submitted, and neither published nor
# dismissed. Left on the old table they would answer "nothing in flight" for every scrape.


async def jurisdiction_ocdids_with_open_changesets(state_code: str) -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT DISTINCT changesets.jurisdiction_ocdid
            FROM changesets
            WHERE {WORK_IN_FLIGHT}
              AND changesets.jurisdiction_ocdid LIKE %s
            """,
            (f"%state:{state_code}%",),
        )
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def has_open_changeset(jurisdiction_ocdid: str) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT 1
            FROM changesets
            WHERE {WORK_IN_FLIGHT}
              AND changesets.jurisdiction_ocdid = %s
            LIMIT 1
            """,
            (jurisdiction_ocdid,),
        )
        return (await cur.fetchone()) is not None
