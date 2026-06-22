from core.coverage import classify_map_status
from database.database import get_pool


async def get_maps_coverage() -> dict:
    """Return total/covered/covered_fresh counts by county and state, grouped by state.

    County counts come from parent_ocdids stored in jurisdictions.data; the array
    contains all OCD ancestors (county, state, etc.) so we filter to county OCDs.
    State counts are computed directly from j.state.

    - `covered`       = has ≥1 current people row (has-data)
    - `covered_fresh` = covered AND scraped_at >= the state's cutoff
    so `stale = covered - covered_fresh` lets the map shade by staleness. The people set
    is pre-aggregated (DISTINCT once) and hash-joined — one pass, not per-row.
    """
    pool = await get_pool()
    has_people_subquery = """
        SELECT DISTINCT jurisdiction_ocdid
        FROM people
        WHERE status = 'current'
    """
    covered_fresh_filter = """
        COUNT(*) FILTER (
            WHERE p.jurisdiction_ocdid IS NOT NULL
              AND j.scraped_at >= COALESCE(sc.min_scraped_at, 'epoch'::timestamptz)
        )::int AS covered_fresh
    """
    async with pool.connection() as conn, conn.cursor() as cur:
        # County-level counts
        await cur.execute(f"""
            SELECT
                j.state,
                parent_ocdid AS county_ocdid,
                COUNT(*)::int       AS total,
                COUNT(p.jurisdiction_ocdid)::int AS covered,
                {covered_fresh_filter}
            FROM jurisdictions j
            CROSS JOIN LATERAL jsonb_array_elements_text(j.data -> 'parent_ocdids') AS parent_ocdid
            LEFT JOIN ({has_people_subquery}) p ON p.jurisdiction_ocdid = j.jurisdiction_ocdid
            LEFT JOIN state_configs sc ON sc.state = j.state
            WHERE j.status = 'current'
              AND j.data ? 'parent_ocdids'
              AND parent_ocdid LIKE '%/county:%'
            GROUP BY j.state, parent_ocdid
            ORDER BY j.state, parent_ocdid
        """)
        county_rows = await cur.fetchall()

        # State-level counts (derived from j.state — no need to store in county_ocdids)
        await cur.execute(f"""
            SELECT
                j.state,
                COUNT(*)::int       AS total,
                COUNT(p.jurisdiction_ocdid)::int AS covered,
                {covered_fresh_filter}
            FROM jurisdictions j
            LEFT JOIN ({has_people_subquery}) p ON p.jurisdiction_ocdid = j.jurisdiction_ocdid
            LEFT JOIN state_configs sc ON sc.state = j.state
            WHERE j.status = 'current'
            GROUP BY j.state
            ORDER BY j.state
        """)
        state_rows = await cur.fetchall()

    result: dict = {}

    for state, total, covered, covered_fresh in state_rows:
        result[state] = {
            "state": {
                "ocdid": f"ocd-jurisdiction/country:us/state:{state}/government",
                "total": total,
                "covered": covered,
                "covered_fresh": covered_fresh,
            },
            "counties": {},
        }

    for state, county_ocdid, total, covered, covered_fresh in county_rows:
        if state in result:
            result[state]["counties"][county_ocdid] = {
                "total": total,
                "covered": covered,
                "covered_fresh": covered_fresh,
            }

    return result


async def get_local_status_for_state(state: str) -> dict[str, str]:
    """ocdid -> map status for every local jurisdiction in `state`.

    Freshness is `scraped_at` vs the state's cutoff (epoch when unset) — the same
    definition the dashboard uses for "done", not `people.updated_at` (which manual
    edits bump). The FRESH/STALE/GAP/UNTRACKED call itself lives in core.coverage.
    """
    query = """
        SELECT
          j.jurisdiction_ocdid,
          EXISTS (
              SELECT 1 FROM people
              WHERE jurisdiction_ocdid = j.jurisdiction_ocdid AND status = 'current'
          ) AS has_people,
          (j.scraped_at IS NOT NULL
           AND j.scraped_at >= COALESCE(sc.min_scraped_at, 'epoch'::timestamptz))
              AS is_fresh,
          NULLIF(j.data->>'url', '') IS NOT NULL AS has_url
        FROM jurisdictions j
        LEFT JOIN state_configs sc ON sc.state = j.state
        WHERE j.status = 'current'
          AND j.state = %s
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (state,))
        rows = await cur.fetchall()
    return {
        jurisdiction_ocdid: classify_map_status(
            has_people=has_people, is_fresh=is_fresh, has_url=has_url
        )
        for jurisdiction_ocdid, has_people, is_fresh, has_url in rows
    }
