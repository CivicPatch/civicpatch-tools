from enum import StrEnum

from database.database import get_pool


class LocalStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    GAP = "gap"
    UNTRACKED = "untracked"


FRESH_THRESHOLD_DAYS = 90


async def get_maps_coverage() -> dict:
    """Return scraped/total counts by county and state, grouped by state.

    County counts come from parent_ocdids stored in jurisdictions.data; the array
    contains all OCD ancestors (county, state, etc.) so we filter to county OCDs.
    State counts are computed directly from j.state.
    A jurisdiction is counted as scraped when it has at least one row in people.
    """
    pool = await get_pool()
    scraped_subquery = """
        SELECT DISTINCT jurisdiction_ocdid
        FROM people
        WHERE status = 'current'
    """
    async with pool.connection() as conn, conn.cursor() as cur:
        # County-level counts
        await cur.execute(f"""
            SELECT
                j.state,
                parent_ocdid AS county_ocdid,
                COUNT(*)::int       AS total,
                COUNT(p.jurisdiction_ocdid)::int AS scraped
            FROM jurisdictions j
            CROSS JOIN LATERAL jsonb_array_elements_text(j.data -> 'parent_ocdids') AS parent_ocdid
            LEFT JOIN ({scraped_subquery}) p ON p.jurisdiction_ocdid = j.jurisdiction_ocdid
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
                COUNT(p.jurisdiction_ocdid)::int AS scraped
            FROM jurisdictions j
            LEFT JOIN ({scraped_subquery}) p ON p.jurisdiction_ocdid = j.jurisdiction_ocdid
            WHERE j.status = 'current'
            GROUP BY j.state
            ORDER BY j.state
        """)
        state_rows = await cur.fetchall()

    result: dict = {}

    for state, total, scraped in state_rows:
        result[state] = {
            "state": {
                "ocdid": f"ocd-jurisdiction/country:us/state:{state}/government",
                "total": total,
                "scraped": scraped,
            },
            "counties": {},
        }

    for state, county_ocdid, total, scraped in county_rows:
        if state in result:
            result[state]["counties"][county_ocdid] = {"total": total, "scraped": scraped}

    return result


async def get_local_status_for_state(state: str) -> dict[str, str]:
    """ocdid -> status for every local jurisdiction in `state`.

    Status is derived from `people.updated_at` (scrape time) and
    `jurisdictions.data->>'url'` (scrapeable). Uses a LATERAL JOIN with the
    existing `idx_people_jurisdiction_ocdid` index for sub-50ms execution.
    """
    query = """
        SELECT
          j.jurisdiction_ocdid,
          CASE
            WHEN p.updated_at >= NOW() - make_interval(days => %s) THEN %s
            WHEN p.updated_at IS NOT NULL                          THEN %s
            WHEN COALESCE(j.data->>'url', '') != ''                THEN %s
            ELSE                                                        %s
          END AS status
        FROM jurisdictions j
        LEFT JOIN LATERAL (
            SELECT MAX(updated_at) AS updated_at
            FROM people
            WHERE jurisdiction_ocdid = j.jurisdiction_ocdid
              AND status = 'current'
        ) p ON true
        WHERE j.status = 'current'
          AND j.state = %s
    """
    params = (
        FRESH_THRESHOLD_DAYS,
        LocalStatus.FRESH.value,
        LocalStatus.STALE.value,
        LocalStatus.GAP.value,
        LocalStatus.UNTRACKED.value,
        state,
    )
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, params)
        rows = await cur.fetchall()
    return {ocdid: status for ocdid, status in rows}
