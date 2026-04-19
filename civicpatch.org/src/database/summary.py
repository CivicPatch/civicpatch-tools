from database.database import get_pool

_OPEN_PRS_GLOBAL = "(SELECT COUNT(*) FROM pull_requests WHERE status = 'open')"

_OPEN_PRS_STATE = """
    (SELECT COUNT(*) FROM pull_requests pr2
     JOIN requests r2 ON r2.id = pr2.request_id
     JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r2.jurisdiction_ocdid
     WHERE pr2.status = 'open' AND jur.state = %s)
"""

_ISSUES_SUBQUERIES_GLOBAL = """
    , (SELECT COUNT(*) FROM pipeline_runs WHERE status = 'ERROR')
    , (SELECT COUNT(*) FROM pipeline_issues WHERE status = 'pending')
    , (SELECT COUNT(*) FROM (
          SELECT r.jurisdiction_ocdid
          FROM pipeline_runs j
          JOIN requests r ON r.id = j.request_id
          JOIN pull_requests pr ON pr.request_id = r.id
          WHERE pr.status = 'open'
          GROUP BY r.jurisdiction_ocdid
          HAVING COUNT(*) > 1
      ) sub)
"""

_ISSUES_SUBQUERIES_STATE = """
    , (SELECT COUNT(*) FROM pipeline_runs prun
       JOIN requests r2 ON r2.id = prun.request_id
       JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r2.jurisdiction_ocdid
       WHERE prun.status = 'ERROR' AND jur.state = %s)
    , (SELECT COUNT(*) FROM pipeline_issues pi2
       WHERE pi2.status = 'pending'
       AND EXISTS (
           SELECT 1 FROM requests r2
           JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r2.jurisdiction_ocdid
           WHERE r2.id::text = ANY(pi2.request_ids) AND jur.state = %s
       ))
    , (SELECT COUNT(*) FROM (
          SELECT r.jurisdiction_ocdid
          FROM pipeline_runs j
          JOIN requests r ON r.id = j.request_id
          JOIN pull_requests pr ON pr.request_id = r.id
          JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
          WHERE pr.status = 'open' AND jur.state = %s
          GROUP BY r.jurisdiction_ocdid
          HAVING COUNT(*) > 1
      ) sub)
"""


async def get_summary_counts(include_issues: bool, state_code: str | None = None) -> dict:
    pool = await get_pool()
    state = state_code.lower() if state_code else None
    if state:
        open_prs_sql = _OPEN_PRS_STATE
        issues_sql = _ISSUES_SUBQUERIES_STATE if include_issues else ""
        params = [state] + ([state, state, state] if include_issues else [])
    else:
        open_prs_sql = _OPEN_PRS_GLOBAL
        issues_sql = _ISSUES_SUBQUERIES_GLOBAL if include_issues else ""
        params = []
    query = f"SELECT {open_prs_sql}{issues_sql}"
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, params)
        row = await cur.fetchone()
    if row is None:
        raise RuntimeError("Summary counts query returned no row")
    result: dict = {"open_prs": row[0]}
    if include_issues:
        result["pipeline_errors"] = row[1]
        result["issues_total"] = row[2]
        result["duplicate_jurisdictions"] = row[3]
    return result
