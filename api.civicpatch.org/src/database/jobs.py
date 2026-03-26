from collections import Counter

from database.database import get_pool, to_iso

async def get_duplicate_jurisdiction_ocdids() -> set:
    """Return a set of jurisdiction_ocdids that appear in more than one open PR."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.jurisdiction_ocdid
            FROM jobs j
            JOIN requests r ON r.job_id = j.id
            JOIN pull_requests pr ON pr.request_id = r.id
            WHERE pr.status = 'open'
            """
        )
        rows = await cur.fetchall()
    ocdids = [r[0] for r in rows if r[0]]
    counts = Counter(ocdids)
    return {ocdid for ocdid, count in counts.items() if count > 1}

async def get_stale_duplicate_pr_info() -> list[dict]:
    """
    For each jurisdiction with more than one open PR, return all but the latest
    (by job created_at). Used for bulk-closing stale duplicates.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            WITH ranked AS (
                SELECT
                    j.request_id,
                    pr.pr_number,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.jurisdiction_ocdid ORDER BY j.created_at DESC
                    ) AS rn
                FROM jobs j
                JOIN requests r ON r.job_id = j.id
                JOIN pull_requests pr ON pr.request_id = r.id
                WHERE pr.status = 'open'
                  AND r.jurisdiction_ocdid IN (
                      SELECT r2.jurisdiction_ocdid
                      FROM jobs j2
                      JOIN requests r2 ON r2.job_id = j2.id
                      JOIN pull_requests pr2 ON pr2.request_id = r2.id
                      WHERE pr2.status = 'open'
                      GROUP BY r2.jurisdiction_ocdid
                      HAVING COUNT(*) > 1
                  )
            )
            SELECT request_id, pr_number FROM ranked WHERE rn > 1
            """
        )
        rows = await cur.fetchall()
    return [{"request_id": r[0], "pr_number": r[1]} for r in rows]


async def get_job_for_review(request_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT pr.url, pr.status, j.pull_request_review_state,
                   r.jurisdiction_ocdid AS jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   j.created_at, j.updated_at
            FROM jobs j
            JOIN requests r ON r.job_id = j.id
            LEFT JOIN pull_requests pr ON pr.request_id = r.id
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
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
