from core.coverage import classify_map_status
from database.people import IS_ON_THE_ROSTER
from database.database import get_pool
from database.jurisdictions import FRESH_SINCE_SQL


async def get_maps_coverage() -> dict:
    """Return total/covered/covered_fresh counts by county and state, grouped by state.

    County counts come from parent_ocdids stored in jurisdictions.data; the array
    contains all OCD ancestors (county, state, etc.) so we filter to county OCDs.
    State counts are computed directly from j.state.

    - `covered`       = has ≥1 current people row (has-data)
    - `covered_fresh` = covered AND scraped within the freshness window
    so `stale = covered - covered_fresh` lets the map shade by staleness. The people set
    is pre-aggregated (DISTINCT once) and hash-joined — one pass, not per-row.
    """
    pool = await get_pool()
    has_people_subquery = f"""
        SELECT DISTINCT jurisdiction_ocdid
        FROM people
        WHERE {IS_ON_THE_ROSTER}
    """
    covered_fresh_filter = f"""
        COUNT(*) FILTER (
            WHERE p.jurisdiction_ocdid IS NOT NULL
              AND j.scraped_at >= {FRESH_SINCE_SQL}
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
            WHERE j.status = 'active'
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
            WHERE j.status = 'active'
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


async def get_municipality_rows_for_state(state: str) -> list[dict]:
    """Name, map status, officials count, and last-verified date for every local jurisdiction
    in `state` — feeds the municipalities list page. Reuses classify_map_status, same as
    get_local_status_for_state, so the two stay consistent by construction.

    `needs_review` isn't included here — it requires the pull_requests domain, which this
    file doesn't own. See services.coverage.get_municipality_list, which composes this with
    the open-PR set (the same to_review signal get_state_coverage below already uses).
    """
    query = f"""
        SELECT
            j.jurisdiction_ocdid,
            j.data->>'name'                                                     AS name,
            COALESCE(pc.people_count, 0)::int                                   AS officials_count,
            j.scraped_at,
            NULLIF(j.data->>'url', '') IS NOT NULL                              AS has_url,
            (j.scraped_at IS NOT NULL
             AND j.scraped_at >= {FRESH_SINCE_SQL})                             AS is_fresh
        FROM jurisdictions j
        LEFT JOIN (
            SELECT jurisdiction_ocdid, COUNT(*)::int AS people_count
            FROM people
            WHERE {IS_ON_THE_ROSTER}
            GROUP BY jurisdiction_ocdid
        ) pc ON pc.jurisdiction_ocdid = j.jurisdiction_ocdid
        WHERE j.status = 'active'
          AND j.level = 'local'
          AND j.state = %s
        ORDER BY j.data->>'name'
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (state,))
        rows = await cur.fetchall()
    return [
        {
            "jurisdiction_ocdid": jurisdiction_ocdid,
            "name": name,
            "status": classify_map_status(
                has_people=officials_count > 0, is_fresh=is_fresh, has_url=has_url
            ),
            "officials_count": officials_count,
            "last_verified_at": scraped_at.isoformat() if scraped_at else None,
        }
        for jurisdiction_ocdid, name, officials_count, scraped_at, has_url, is_fresh in rows
    ]


async def get_local_status_for_state(state: str) -> dict[str, str]:
    """ocdid -> map status for every local jurisdiction in `state`.

    Freshness is `scraped_at` vs the rolling window — the same definition the dashboard
    uses for "done", not `people.updated_at` (which manual edits bump). The
    FRESH/STALE/GAP/UNTRACKED call itself lives in core.coverage.
    """
    query = f"""
        SELECT
          j.jurisdiction_ocdid,
          EXISTS (
              SELECT 1 FROM people
              WHERE jurisdiction_ocdid = j.jurisdiction_ocdid AND status = 'active'
          ) AS has_people,
          (j.scraped_at IS NOT NULL AND j.scraped_at >= {FRESH_SINCE_SQL})
              AS is_fresh,
          NULLIF(j.data->>'url', '') IS NOT NULL AS has_url
        FROM jurisdictions j
        WHERE j.status = 'active'
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
