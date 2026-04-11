import os
from typing import List, Optional

from psycopg import sql
import services.storage_service
import shared.utils.id_utils
import shared.utils.url_utils
from database.database import get_pool, to_iso


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
