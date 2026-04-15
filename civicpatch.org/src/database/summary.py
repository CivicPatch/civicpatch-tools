from database.database import get_pool


async def get_summary_counts(include_issues: bool) -> dict:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM pull_requests WHERE status = 'open') AS open_prs,
                (SELECT COUNT(*) FROM pipeline_runs WHERE status = 'ERROR') AS pipeline_errors,
                (SELECT COUNT(*) FROM pipeline_issues WHERE status = 'pending') AS issues_total,
                (SELECT COUNT(*) FROM (
                    SELECT r.jurisdiction_ocdid
                    FROM pipeline_runs j
                    JOIN requests r ON r.id = j.request_id
                    JOIN pull_requests pr ON pr.request_id = r.id
                    WHERE pr.status = 'open'
                    GROUP BY r.jurisdiction_ocdid
                    HAVING COUNT(*) > 1
                ) sub) AS duplicate_jurisdictions
            """
        )
        row = await cur.fetchone()
    if row is None:
        raise RuntimeError("Summary counts query returned no row")
    result: dict = {"open_prs": row[0]}
    if include_issues:
        result["pipeline_errors"] = row[1]
        result["issues_total"] = row[2]
        result["duplicate_jurisdictions"] = row[3]
    return result
