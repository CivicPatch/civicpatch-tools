import os
from typing import List, Optional

from psycopg import sql
import services.storage_service
import shared.utils.id_utils
import shared.utils.url_utils
from database.database import get_pool, to_iso
from utils.github_utils import pull_request_url_to_number


async def list_open_pull_requests(
    state_code: Optional[str] = None,
    jurisdiction_ocdid: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[List[dict], int, int]:
    conditions: list[sql.Composable] = [sql.SQL("pr.status = 'open'")]
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
                   COUNT(*) FILTER (WHERE jsonb_array_length(r.review_json->'issues') > 0)
            FROM pull_requests pr
            JOIN requests r ON r.id = pr.request_id
            {}
            """).format(where),
            params,
        )
        count_row = await cur.fetchone()
        total, with_issues = count_row if count_row is not None else (0, 0)

        await cur.execute(
            sql.SQL("""
            SELECT pr.request_id::text, pr.url, pr.status,
                   r.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   pr.created_at, pr.review_state,
                   COALESCE(jsonb_array_length(r.review_json->'issues'), 0) AS issue_count,
                   pr.pr_number
            FROM pull_requests pr
            JOIN requests r ON r.id = pr.request_id
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            {}
            ORDER BY jsonb_array_length(r.review_json->'issues') DESC NULLS LAST, pr.created_at DESC
            LIMIT %s OFFSET %s
            """).format(where),
            params + [per_page, offset],
        )
        rows = await cur.fetchall()

    results = [
        {
            "request_id": r[0],
            "created_at": to_iso(r[5]),
            "issue_count": r[7],
            "jurisdiction": {"ocdid": r[3], "name": r[4], "path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(r[3])},
            "pr": {"url": r[1], "status": r[2], "review_state": r[6], "number": r[8]},
        }
        for r in rows
    ]
    return results, total, with_issues


async def get_pull_request_for_review(request_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT pr.url, pr.status, pr.review_state,
                   r.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   pr.pr_number
            FROM pull_requests pr
            JOIN requests r ON r.id = pr.request_id
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE pr.request_id = %s
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "request_id": request_id,
            "jurisdiction": {"ocdid": row[3], "name": row[4]},
            "pr": {"url": row[0], "status": row[1], "review_state": row[2], "number": row[5]},
        }


def _source_url_to_markdown_url(request_id: str, jurisdiction_ocdid_folder: str, source_url: str) -> str:
    source_url_dir = shared.utils.url_utils.format_url_to_folder(source_url)
    relative_path = os.path.join(request_id, "data_source", jurisdiction_ocdid_folder, "cache", source_url_dir, "preprocessed.md")
    return services.storage_service.get_civicpatch_artifacts_url(relative_path)


def build_sources(request_id: str, jurisdiction_ocdid: str, source_urls: list[str]) -> list[dict]:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return [
        {
            "url": url,
            "markdown": _source_url_to_markdown_url(request_id, folder, url),
        }
        for url in source_urls
    ]


async def update_job_pull_request_url(request_id: str, pull_request_url: str | None = None):
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


async def update_job_pull_request_status(
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


async def update_job_pull_request_review_state(request_id: str, review_state: str | None):
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
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            JOIN pull_requests pr ON pr.request_id = r.id
            WHERE pr.status = 'open'
            """
        )
        rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}


async def bulk_close_stale_prs(request_ids: List[str]):
    if not request_ids:
        return
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pull_requests pr
            SET status = 'closed', updated_at = CURRENT_TIMESTAMP
            FROM jobs j
            WHERE pr.request_id = j.request_id AND j.request_id = ANY(%s)
            """,
            (request_ids,),
        )
