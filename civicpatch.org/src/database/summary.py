from database.database import get_pool
from database.changesets import AVAILABLE_FOR_REVIEW

_OPEN_PRS_GLOBAL = f"""
    (SELECT COUNT(*) FROM changesets r
     WHERE {AVAILABLE_FOR_REVIEW})
"""

_OPEN_PRS_STATE = f"""
    (SELECT COUNT(*) FROM changesets r
     JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
     WHERE {AVAILABLE_FOR_REVIEW} AND jur.state = %s)
"""

_ISSUES_SUBQUERIES_GLOBAL = """
    , (SELECT COUNT(*) FROM issues WHERE status IN ('pending', 'pr_opened'))
"""

_ISSUES_SUBQUERIES_STATE = """
    , (SELECT COUNT(*) FROM issues pi2
       WHERE pi2.status IN ('pending', 'pr_opened')
       AND EXISTS (
           SELECT 1 FROM changesets r2
           JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r2.jurisdiction_ocdid
           WHERE r2.id::text = ANY(pi2.changeset_ids) AND jur.state = %s
       ))
"""


async def get_summary_counts(include_issues: bool, state_code: str | None = None) -> dict:
    pool = await get_pool()
    state = state_code.lower() if state_code else None
    if state:
        open_prs_sql = _OPEN_PRS_STATE
        issues_sql = _ISSUES_SUBQUERIES_STATE if include_issues else ""
        params = [state] + ([state] if include_issues else [])
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
        result["issues_total"] = row[1]
    return result
