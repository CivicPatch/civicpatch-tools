from database.database import get_pool
from database.freshness import FRESH_SINCE_SQL


async def get_dashboard() -> dict:
    """Per-state counts of local jurisdictions and CivicPatch coverage.

    Shape matches the legacy dashboard.json contract consumed by the
    progress-dashboard frontend components, minus the deprecated external/*
    fields. `covered` = covered_fresh + covered_stale; the fresh/stale split powers the
    new bar + staleness-aware map color.

    `status_counts` mirrors `classify_map_status` (core/coverage.py) and the homepage
    status taxonomy (fresh/stale/gap/untracked). `cutoff` is the start of the rolling
    freshness window — the same for every state, kept per-state in the response shape
    for the frontend's sake. `covered_fresh`/`covered_stale`
    additionally require `has_url` (the "legacy" coverage view is scrapeable-only);
    `status_fresh`/`status_stale` don't, matching `classify_map_status`'s actual branches —
    these two families genuinely diverge on jurisdictions with people but no URL on file
    (10 rows in prod as of writing), so both are real, not just aliases of each other.
    `has_url`/`has_people`/`is_fresh` are computed once per jurisdiction in `local_flags`;
    every count below is just a combination of those three booleans, not a re-derivation.

    People are joined pre-aggregated (one GROUP BY over people, hash-joined) rather
    than a per-row correlated subquery — this scans all states once, so it stays a
    couple of passes even at tens of thousands of jurisdictions.
    """
    query = f"""
        WITH local_flags AS (
            SELECT
                j.state,
                COALESCE(pc.people_count, 0)                                      AS people_count,
                NULLIF(j.data->>'url', '') IS NOT NULL                            AS has_url,
                COALESCE(pc.people_count, 0) > 0                                  AS has_people,
                -- NULL guard: a bare comparison yields NULL, which no FILTER below counts.
                -- scraped_at is only stamped on job-PR merge, so officials that arrived
                -- via open-data sync alone stay NULL.
                (j.scraped_at IS NOT NULL
                 AND j.scraped_at >= {FRESH_SINCE_SQL})                           AS is_fresh
            FROM jurisdictions j
            LEFT JOIN (
                SELECT jurisdiction_ocdid, COUNT(*)::int AS people_count
                FROM people
                WHERE status = 'active'
                GROUP BY jurisdiction_ocdid
            ) pc ON pc.jurisdiction_ocdid = j.jurisdiction_ocdid
            WHERE j.status = 'active'
              AND j.level = 'local'
        )
        SELECT
            state,
            COUNT(*)::int                                                     AS known,
            COUNT(*) FILTER (WHERE has_url)::int                               AS scrapeable,
            COUNT(*) FILTER (WHERE has_url AND has_people AND is_fresh)::int   AS covered_fresh,
            COUNT(*) FILTER (
                WHERE has_url AND has_people AND NOT is_fresh
            )::int                                                            AS covered_stale,
            SUM(people_count)::int                                            AS officials,
            COUNT(*) FILTER (WHERE has_people AND is_fresh)::int              AS status_fresh,
            COUNT(*) FILTER (WHERE has_people AND NOT is_fresh)::int          AS status_stale,
            COUNT(*) FILTER (WHERE NOT has_people AND has_url)::int           AS status_gap,
            COUNT(*) FILTER (WHERE NOT has_people AND NOT has_url)::int       AS status_untracked,
            {FRESH_SINCE_SQL}                                                 AS cutoff
        FROM local_flags
        GROUP BY state
        ORDER BY state
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query)
        rows = await cur.fetchall()

    states: dict = {}
    for (
        state, known, scrapeable, covered_fresh, covered_stale, officials,
        status_fresh, status_stale, status_gap, status_untracked, cutoff,
    ) in rows:
        states[state] = {
            "state": state,
            "civicpatch": {
                "officials": officials,
                "cutoff": cutoff.isoformat(),
                "localities": {
                    "known": known,
                    "scrapeable": scrapeable,
                    "covered": covered_fresh + covered_stale,
                    "covered_fresh": covered_fresh,
                    "covered_stale": covered_stale,
                },
                "status_counts": {
                    "fresh": status_fresh,
                    "stale": status_stale,
                    "gap": status_gap,
                    "untracked": status_untracked,
                },
            },
        }
    return {"states": states}
