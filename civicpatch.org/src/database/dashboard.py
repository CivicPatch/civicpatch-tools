from database.database import get_pool


async def get_dashboard() -> dict:
    """Per-state counts of local jurisdictions and CivicPatch coverage.

    Shape matches the legacy dashboard.json contract consumed by the
    progress-dashboard frontend components, minus the deprecated external/*
    fields.
    """
    query = """
        SELECT
            j.state,
            COUNT(*)::int                                                       AS known,
            COUNT(*) FILTER (WHERE COALESCE(j.data->>'url', '') != '')::int     AS scrapeable,
            COUNT(*) FILTER (WHERE p.people_count > 0)::int                     AS coverage,
            COALESCE(SUM(p.people_count), 0)::int                               AS officials
        FROM jurisdictions j
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::int AS people_count
            FROM people
            WHERE jurisdiction_ocdid = j.jurisdiction_ocdid
              AND status = 'current'
        ) p ON true
        WHERE j.status = 'current'
          AND j.level = 'local'
        GROUP BY j.state
        ORDER BY j.state
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query)
        rows = await cur.fetchall()

    states: dict = {}
    for state, known, scrapeable, coverage, officials in rows:
        states[state] = {
            "state": state,
            "civicpatch": {
                "officials": officials,
                "localities": {
                    "known": known,
                    "scrapeable": scrapeable,
                    "coverage": coverage,
                },
            },
        }
    return {"states": states}
