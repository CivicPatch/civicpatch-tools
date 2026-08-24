from typing import List, Optional

from psycopg import sql
import shared.utils.id_utils
from shared.utils.statuses import (
    RequestType,
)
from database.database import get_pool, to_iso
from database.requests import AVAILABLE_FOR_REVIEW, REVIEW_STATUS, WORK_IN_FLIGHT
from database.review_queue import issue_count, issue_priority
from lib.github.utils import pull_request_url_to_number



async def list_open_pull_requests(
    state_code: Optional[str] = None,
    jurisdiction_ocdid: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[List[dict], int, int]:
    conditions: list[sql.Composable] = [sql.SQL(AVAILABLE_FOR_REVIEW)]
    params: list = []

    if jurisdiction_ocdid:
        conditions.append(sql.SQL("r.jurisdiction_ocdid = %s"))
        params.append(jurisdiction_ocdid)
    elif state_code:
        conditions.append(sql.SQL("r.jurisdiction_ocdid LIKE %s"))
        params.append(f"%state:{state_code}%")

    where = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(conditions))
    offset = (page - 1) * per_page

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE {count} > 0)
            FROM requests r
            {}
            """).format(
                where,
                count=sql.SQL(issue_count("r.review_json", "r.jurisdiction_ocdid")),
            ),
            params,
        )
        count_row = await cur.fetchone()
        total, with_issues = count_row if count_row is not None else (0, 0)

        await cur.execute(
            sql.SQL("""
            SELECT r.id::text, r.open_data_url, {status},
                   r.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   r.created_at,
                   {count} AS issue_count
            FROM requests r
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            {}
            ORDER BY {priority} DESC, r.created_at DESC
            LIMIT %s OFFSET %s
            """).format(where, status=sql.SQL(REVIEW_STATUS),
                        count=sql.SQL(issue_count("r.review_json", "r.jurisdiction_ocdid")),
                        priority=sql.SQL(issue_priority("r.review_json", "r.jurisdiction_ocdid"))),
            params + [per_page, offset],
        )
        rows = await cur.fetchall()

    results = [
        {
            "request_id": r[0],
            "created_at": to_iso(r[5]),
            "issue_count": r[6],
            "jurisdiction": {"ocdid": r[3], "name": r[4], "path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(r[3])},
            "pr": {"url": r[1], "status": r[2]},
        }
        for r in rows
    ]
    return results, total, with_issues


async def get_pull_request_for_review(request_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT r.open_data_url, {REVIEW_STATUS},
                   r.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   jur.data->>'url' AS jurisdiction_website_url
            FROM requests r
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.id = %s AND r.request_type != %s
            """,
            (request_id, RequestType.JURISDICTION_MANUAL_EDIT),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "request_id": request_id,
            "jurisdiction": {
                "ocdid": row[2],
                "name": row[3],
                "path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(row[2]),
                "website_url": row[4],
            },
            # `review_state` and `number` are gone: the first never had a writer, and the
            # second no longer identifies anything — publishing is keyed on the request.
            "pr": {
                "url": row[0],
                "status": row[1],
            },
        }



async def get_pull_request_data_by_request_id(request_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT r.id::text, r.open_data_url, {REVIEW_STATUS},
                   r.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   COALESCE(r.data_json, '[]'::jsonb) AS data_json,
                   jur.data->>'url' AS jurisdiction_website_url
            FROM requests r
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.id::text = %s AND r.request_type != %s
            """,
            (request_id, RequestType.JURISDICTION_MANUAL_EDIT),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "request_id": row[0],
            "jurisdiction_ocdid": row[3],
            "jurisdiction_name": row[4],
            "jurisdiction_website_url": row[6],
            "pr": {"url": row[1], "status": row[2]},
            "proposed": row[5] if row[5] is not None else [],
        }


async def update_pipeline_run_pull_request_url(request_id: str, pull_request_url: str | None = None):
    pool = await get_pool()
    pr_number = 0
    if pull_request_url:
        num = pull_request_url_to_number(pull_request_url)
        pr_number = int(num) if num else 0

    async with pool.connection() as conn:
        result = await conn.execute(
            """
            INSERT INTO pull_requests (request_id, url, status, pr_number, created_at, updated_at)
            VALUES (%s, %s, 'open', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (request_id) DO UPDATE
                SET url = EXCLUDED.url,
                    status = CASE
                        WHEN pull_requests.status IN ('merged', 'closed') THEN pull_requests.status
                        ELSE 'open'
                    END,
                    updated_at = CURRENT_TIMESTAMP
            """,
            (request_id, pull_request_url, pr_number),
        )
        return result.rowcount > 0


async def update_pull_request_status(
    request_id: str,
    pull_request_status: str,
    pull_request_merged_at=None,
    pull_request_url: Optional[str] = None,
    resolved_by_user_id: Optional[str] = None,
) -> bool:
    pool = await get_pool()
    pr_number = 0
    if pull_request_url:
        num = pull_request_url_to_number(pull_request_url)
        pr_number = int(num) if num else 0

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1 FROM requests WHERE id = %s", (request_id,))
        if not await cur.fetchone():
            return False
        await cur.execute(
            """
            INSERT INTO pull_requests (request_id, url, status, merged_at, pr_number, resolved_by_user_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (request_id) DO UPDATE
                SET status = EXCLUDED.status,
                    merged_at = EXCLUDED.merged_at,
                    url = COALESCE(EXCLUDED.url, pull_requests.url),
                    resolved_by_user_id = EXCLUDED.resolved_by_user_id,
                    updated_at = CURRENT_TIMESTAMP
            """,
            (request_id, pull_request_url, pull_request_status, pull_request_merged_at, pr_number, resolved_by_user_id),
        )
        return True


async def get_pull_request_status(request_id: str) -> Optional[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT status FROM pull_requests WHERE request_id = %s", (request_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_merge_enqueued(request_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pull_requests
            SET merge_enqueued_at = now(),
                updated_at = CURRENT_TIMESTAMP
            WHERE request_id::text = %s;
            """,
            (request_id,),
        )


async def clear_merge_enqueued(request_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pull_requests
            SET merge_enqueued_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE request_id::text = %s;
            """,
            (request_id,),
        )


async def update_pipeline_run_pull_request_review_state(request_id: str, review_state: str | None):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pull_requests
            SET review_state = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE request_id = %s;
            """,
            (review_state, request_id),
        )


async def get_open_pr_request_ids() -> dict[str, str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.request_id, pr.url
            FROM pipeline_runs j
            JOIN requests r ON r.id = j.request_id
            JOIN pull_requests pr ON pr.request_id = r.id
            WHERE pr.status = 'open' AND r.request_type != %s
            """,
            (RequestType.JURISDICTION_MANUAL_EDIT,),
        )
        rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}


# These two answer "is there already work in flight for this jurisdiction?" — they gate
# starting a duplicate scrape, choosing the next scrape candidate, and the coverage figure.
# They asked GitHub because an open pull request used to BE that state. Nothing opens one now,
# so the question is a plain test on the request: submitted, and neither published nor
# dismissed. Left on pull_requests they would answer "nothing in flight" for every scrape.


async def get_open_pr_ocdids_by_state(state_code: str) -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT DISTINCT r.jurisdiction_ocdid
            FROM requests r
            WHERE {WORK_IN_FLIGHT}
              AND r.jurisdiction_ocdid LIKE %s
            """,
            (f"%state:{state_code}%",),
        )
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def has_open_pr_for_jurisdiction(jurisdiction_ocdid: str) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT 1
            FROM requests r
            WHERE {WORK_IN_FLIGHT}
              AND r.jurisdiction_ocdid = %s
            LIMIT 1
            """,
            (jurisdiction_ocdid,),
        )
        return (await cur.fetchone()) is not None


async def bulk_close_stale_prs(request_ids: List[str]):
    if not request_ids:
        return
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pull_requests pr
            SET status = 'closed', updated_at = CURRENT_TIMESTAMP
            FROM pipeline_runs j
            WHERE pr.request_id = j.request_id AND j.request_id = ANY(%s)
            """,
            (request_ids,),
        )
