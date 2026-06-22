from database.database import get_pool


async def get_dashboard() -> dict:
    """Per-state counts of local jurisdictions and CivicPatch coverage.

    Shape matches the legacy dashboard.json contract consumed by the
    progress-dashboard frontend components, minus the deprecated external/*
    fields. `covered` = covered_fresh + covered_stale; the fresh/stale split powers the
    new bar + staleness-aware map color.

    People are joined pre-aggregated (one GROUP BY over people, hash-joined) rather
    than a per-row correlated subquery — this scans all states once, so it stays a
    couple of passes even at tens of thousands of jurisdictions.
    """
    query = """
        SELECT
            j.state,
            COUNT(*)::int                                                   AS known,
            COUNT(*) FILTER (
                WHERE NULLIF(j.data->>'url', '') IS NOT NULL
            )::int                                                          AS scrapeable,
            COUNT(*) FILTER (
                WHERE NULLIF(j.data->>'url', '') IS NOT NULL
                  AND pc.people_count > 0
                  AND j.scraped_at >= COALESCE(sc.min_scraped_at, 'epoch'::timestamptz)
            )::int                                                          AS covered_fresh,
            COUNT(*) FILTER (
                WHERE NULLIF(j.data->>'url', '') IS NOT NULL
                  AND pc.people_count > 0
                  AND (j.scraped_at IS NULL
                       OR j.scraped_at < COALESCE(sc.min_scraped_at, 'epoch'::timestamptz))
            )::int                                                          AS covered_stale,
            COALESCE(SUM(pc.people_count), 0)::int                          AS officials
        FROM jurisdictions j
        LEFT JOIN state_configs sc ON sc.state = j.state
        LEFT JOIN (
            SELECT jurisdiction_ocdid, COUNT(*)::int AS people_count
            FROM people
            WHERE status = 'current'
            GROUP BY jurisdiction_ocdid
        ) pc ON pc.jurisdiction_ocdid = j.jurisdiction_ocdid
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
    for state, known, scrapeable, covered_fresh, covered_stale, officials in rows:
        states[state] = {
            "state": state,
            "civicpatch": {
                "officials": officials,
                "localities": {
                    "known": known,
                    "scrapeable": scrapeable,
                    "covered": covered_fresh + covered_stale,
                    "covered_fresh": covered_fresh,
                    "covered_stale": covered_stale,
                },
            },
        }
    return {"states": states}
