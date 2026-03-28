from typing import List, Optional

from database.database import get_pool, to_iso


async def list_open_pull_requests(
    state_code: Optional[str] = None,
    jurisdiction_ocdid: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[List[dict], int, int]:
    conditions = ["pr.status = 'open'"]
    params: list = []

    if jurisdiction_ocdid:
        conditions.append("r.jurisdiction_ocdid = %s")
        params.append(jurisdiction_ocdid)
    elif state_code:
        conditions.append("r.jurisdiction_ocdid LIKE %s")
        params.append(f"%state:{state_code}%")

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE pr.review_state = 'changes_requested')
            FROM pull_requests pr
            JOIN requests r ON r.id = pr.request_id
            WHERE {where}
            """,
            params,
        )
        total, changes_requested = await cur.fetchone()

        await cur.execute(
            f"""
            SELECT pr.request_id, pr.url, pr.status,
                   r.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   pr.created_at, pr.updated_at, pr.review_state
            FROM pull_requests pr
            JOIN requests r ON r.id = pr.request_id
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE {where}
            ORDER BY (pr.review_state = 'changes_requested') DESC, pr.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
        )
        rows = await cur.fetchall()

    results = [
        {
            "request_id": r[0],
            "pull_request_url": r[1],
            "pull_request_status": r[2],
            "jurisdiction_ocdid": r[3],
            "jurisdiction_name": r[4],
            "created_at": to_iso(r[5]),
            "updated_at": to_iso(r[6]),
            "pull_request_review_state": r[7],
        }
        for r in rows
    ]
    return results, total, changes_requested

async def get_pull_request_for_review(request_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT pr.url, pr.status, pr.review_state,
                   r.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   pr.created_at, pr.updated_at
            FROM pull_requests pr
            JOIN requests r ON r.id = pr.request_id
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE pr.request_id = %s
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None, None
        return {
            "request_id": request_id,
            "pull_request_url": row[0],
            "pull_request_status": row[1],
            "pull_request_review_state": row[2],
            "jurisdiction_ocdid": row[3],
            "jurisdiction_name": row[4],
            "created_at": to_iso(row[5]),
            "updated_at": to_iso(row[6]),
        } 
