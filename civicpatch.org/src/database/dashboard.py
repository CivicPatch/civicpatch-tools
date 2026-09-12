from database.changeset_predicates import (
    AVAILABLE_FOR_REVIEW,
    LAST_COLLECTED_AT,
    LAST_COLLECTED_JOIN,
)
from database.database import get_pool
from database.jurisdictions import FRESH_SINCE_SQL
from database.people import IS_ON_THE_ROSTER


async def get_dashboard() -> dict:
    query = f"""
        WITH local_flags AS (
            SELECT
                j.state,
                j.level,
                COALESCE(pc.people_count, 0)                                      AS people_count,
                NULLIF(j.data->>'url', '') IS NOT NULL                            AS has_url,
                COALESCE(pc.people_count, 0) > 0                                  AS has_people,
                -- NULL guard: a bare comparison yields NULL, which no FILTER below counts.
                -- Derived from published collection changesets, so officials that arrived
                -- via open-data sync alone stay NULL.
                ({LAST_COLLECTED_AT} IS NOT NULL
                 AND {LAST_COLLECTED_AT} >= {FRESH_SINCE_SQL})                    AS is_fresh
            FROM jurisdictions j
            {LAST_COLLECTED_JOIN}
            LEFT JOIN (
                SELECT jurisdiction_ocdid, COUNT(*)::int AS people_count
                FROM people
                WHERE {IS_ON_THE_ROSTER}
                GROUP BY jurisdiction_ocdid
            ) pc ON pc.jurisdiction_ocdid = j.jurisdiction_ocdid
            -- 'counties' is a real local tier, not a rollup of 'local' — Hawaii has no
            -- municipal governments at all, so excluding it left Hawaii with zero rows
            -- and no entry in the response, not just an undercount like every other
            -- state with a 'counties' tier.
            WHERE j.status = 'active'
              AND j.level IN ('local', 'counties')
        ),
        review_counts AS (
            SELECT j.state, COUNT(*)::int AS needs_review
            FROM changesets
            JOIN jurisdictions j ON j.jurisdiction_ocdid = changesets.jurisdiction_ocdid
            WHERE {AVAILABLE_FOR_REVIEW}
            GROUP BY j.state
        )
        SELECT
            lf.state,
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
            COALESCE(MAX(rc.needs_review), 0)                                 AS needs_review,
            {FRESH_SINCE_SQL}                                                 AS cutoff,
            -- Split out by level too, for the freshness widget's separate municipalities/
            -- counties bars — the merged columns above stay as-is for the map and the
            -- home-page leaderboard, which deliberately don't distinguish the two tiers.
            COUNT(*) FILTER (WHERE level = 'local')::int                        AS muni_known,
            COUNT(*) FILTER (WHERE level = 'local' AND has_people AND is_fresh)::int
                                                                               AS muni_fresh,
            COUNT(*) FILTER (WHERE level = 'local' AND has_people AND NOT is_fresh)::int
                                                                               AS muni_stale,
            COUNT(*) FILTER (WHERE level = 'local' AND NOT has_people AND has_url)::int
                                                                               AS muni_gap,
            COUNT(*) FILTER (
                WHERE level = 'local' AND NOT has_people AND NOT has_url
            )::int                                                            AS muni_untracked,
            COUNT(*) FILTER (WHERE level = 'counties')::int                     AS county_known,
            COUNT(*) FILTER (WHERE level = 'counties' AND has_people AND is_fresh)::int
                                                                               AS county_fresh,
            COUNT(*) FILTER (WHERE level = 'counties' AND has_people AND NOT is_fresh)::int
                                                                               AS county_stale,
            COUNT(*) FILTER (WHERE level = 'counties' AND NOT has_people AND has_url)::int
                                                                               AS county_gap,
            COUNT(*) FILTER (
                WHERE level = 'counties' AND NOT has_people AND NOT has_url
            )::int                                                            AS county_untracked
        FROM local_flags lf
        LEFT JOIN review_counts rc ON rc.state = lf.state
        GROUP BY lf.state
        ORDER BY lf.state
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query)
        rows = await cur.fetchall()

    states: dict = {}
    for (
        state,
        known,
        scrapeable,
        covered_fresh,
        covered_stale,
        officials,
        status_fresh,
        status_stale,
        status_gap,
        status_untracked,
        needs_review,
        cutoff,
        muni_known,
        muni_fresh,
        muni_stale,
        muni_gap,
        muni_untracked,
        county_known,
        county_fresh,
        county_stale,
        county_gap,
        county_untracked,
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
                "needs_review": needs_review,
                "municipalities": {
                    "known": muni_known,
                    "status_counts": {
                        "fresh": muni_fresh,
                        "stale": muni_stale,
                        "gap": muni_gap,
                        "untracked": muni_untracked,
                    },
                },
                "counties": {
                    "known": county_known,
                    "status_counts": {
                        "fresh": county_fresh,
                        "stale": county_stale,
                        "gap": county_gap,
                        "untracked": county_untracked,
                    },
                },
            },
        }
    return {"states": states}
