from database.database import get_pool, to_iso
from collections import Counter
async def get_duplicate_jurisdiction_ocdids() -> set:
    """Return a set of jurisdiction_ocdids that appear in more than one open PR."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.jurisdiction_ocdid AS jurisdiction_ocdid
            FROM jobs j
            WHERE j.pull_request_status = 'open'
            """
        )
        rows = await cur.fetchall()
    ocdids = [r[0] for r in rows if r[0]]
    counts = Counter(ocdids)
    return {ocdid for ocdid, count in counts.items() if count > 1}

async def get_job_for_review(request_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.pull_request_url, j.pull_request_status, j.pull_request_review_state,
                   j.jurisdiction_ocdid AS jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   j.created_at, j.updated_at
            FROM jobs j
            LEFT JOIN jurisdictions jur
                ON jur.jurisdiction_ocdid = j.jurisdiction_ocdid
            WHERE j.request_id = %s
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
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
