from typing import Any
from database.database import get_pool
from database.changeset_predicates import AVAILABLE_FOR_REVIEW
from psycopg.rows import namedtuple_row
from shared.utils.date_utils import STREAK_TIMEZONE


async def get_leaderboard() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=namedtuple_row) as cur:
            await cur.execute(
                """
                WITH counts AS (
                    SELECT
                        rs.state_code,
                        COALESCE(u.display_name, 'Anonymous') AS display_name,
                        u.provider,
                        u.provider_user_id,
                        COUNT(*) AS resolved_count
                    FROM review_session_entries rse
                    JOIN review_sessions rs ON rs.id = rse.review_session_id
                    JOIN users u ON u.id = rs.user_id
                    WHERE rse.status = 'resolved'
                    GROUP BY rs.state_code, u.id, u.display_name, u.provider, u.provider_user_id
                ),
                ranked AS (
                    SELECT
                        state_code,
                        display_name,
                        provider,
                        provider_user_id,
                        resolved_count,
                        ROW_NUMBER() OVER (
                            PARTITION BY state_code
                            ORDER BY resolved_count DESC
                        ) AS rn
                    FROM counts
                )
                SELECT state_code, display_name, provider, provider_user_id, resolved_count
                FROM ranked
                WHERE rn = 1
                ORDER BY state_code
                """
            )
            rows = await cur.fetchall()
    return [
        {
            "state_code": row.state_code,  # type: ignore[union-attr]
            "display_name": row.display_name,  # type: ignore[union-attr]
            "provider": row.provider,  # type: ignore[union-attr]
            "provider_user_id": row.provider_user_id,  # type: ignore[union-attr]
            "resolved_count": row.resolved_count,  # type: ignore[union-attr]
        }
        for row in rows
    ]


async def get_review_stats(
    user_id: str,
    state_code: str,
) -> dict[str, Any]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=namedtuple_row) as cur:
            await cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (
                        WHERE (rse.created_at AT TIME ZONE %s)::date = (NOW() AT TIME ZONE %s)::date
                    ) AS today_resolved,
                    COUNT(*) AS all_time_resolved,
                    (NOW() AT TIME ZONE %s)::date AS current_date
                FROM review_session_entries rse
                JOIN review_sessions rs ON rs.id = rse.review_session_id
                WHERE rs.user_id = %s
                  AND rse.status = 'resolved'
                """,
                (STREAK_TIMEZONE, STREAK_TIMEZONE, STREAK_TIMEZONE, user_id),
            )
            stats = await cur.fetchone()

            await cur.execute(
                """
                WITH daily AS (
                    SELECT DISTINCT (rse.created_at AT TIME ZONE %s)::date AS activity_date
                    FROM review_session_entries rse
                    JOIN review_sessions rs ON rs.id = rse.review_session_id
                    WHERE rs.user_id = %s
                      AND rse.status = 'resolved'
                      AND (rse.created_at AT TIME ZONE %s)::date >= (NOW() AT TIME ZONE %s)::date - INTERVAL '365 days'
                ),
                grouped AS (
                    SELECT activity_date,
                           activity_date - (ROW_NUMBER() OVER (ORDER BY activity_date))::int AS grp
                    FROM daily
                ),
                streaks AS (
                    SELECT COUNT(*) AS length, MAX(activity_date) AS last_day
                    FROM grouped
                    GROUP BY grp
                )
                SELECT length FROM streaks
                WHERE last_day >= (NOW() AT TIME ZONE %s)::date - 1
                ORDER BY last_day DESC
                LIMIT 1
                """,
                (STREAK_TIMEZONE, user_id, STREAK_TIMEZONE, STREAK_TIMEZONE, STREAK_TIMEZONE),
            )
            streak_row = await cur.fetchone()

            await cur.execute(
                f"""
                SELECT COUNT(*) AS available_count
                FROM changesets
                WHERE {AVAILABLE_FOR_REVIEW}
                  AND changesets.jurisdiction_ocdid LIKE %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM review_session_entries rse
                      JOIN review_sessions rs ON rs.id = rse.review_session_id
                      WHERE rse.jurisdiction_ocdid = changesets.jurisdiction_ocdid
                        AND rse.status = 'claimed'
                        AND rs.user_id != %s
                  )
                """,
                (f"%state:{state_code}%", user_id),
            )
            available = await cur.fetchone()

            await cur.execute(
                """
                SELECT COUNT(*) AS claimed_count
                FROM review_session_entries rse
                JOIN review_sessions rs ON rs.id = rse.review_session_id
                WHERE rs.user_id = %s
                  AND rs.state_code = %s
                  AND rse.status NOT IN ('resolved')
                """,
                (user_id, state_code),
            )
            claimed = await cur.fetchone()

            await cur.execute(
                """
                SELECT activity_date::text AS date, COUNT(*) AS count
                FROM (
                    SELECT (rse.created_at AT TIME ZONE %s)::date AS activity_date
                    FROM review_session_entries rse
                    JOIN review_sessions rs ON rs.id = rse.review_session_id
                    WHERE rs.user_id = %s
                      AND rse.status = 'resolved'
                      AND (rse.created_at AT TIME ZONE %s)::date >= (NOW() AT TIME ZONE %s)::date - INTERVAL '16 weeks'
                ) sub
                GROUP BY activity_date
                ORDER BY activity_date
                """,
                (STREAK_TIMEZONE, user_id, STREAK_TIMEZONE, STREAK_TIMEZONE),
            )
            daily_rows = await cur.fetchall()

            await cur.execute(
                """
                WITH daily AS (
                    SELECT DISTINCT (rse.created_at AT TIME ZONE %s)::date AS activity_date
                    FROM review_session_entries rse
                    JOIN review_sessions rs ON rs.id = rse.review_session_id
                    WHERE rs.user_id = %s
                      AND rse.status = 'resolved'
                ),
                grouped AS (
                    SELECT activity_date,
                           activity_date - (ROW_NUMBER() OVER (ORDER BY activity_date))::int AS grp
                    FROM daily
                ),
                streaks AS (
                    SELECT COUNT(*) AS length
                    FROM grouped
                    GROUP BY grp
                )
                SELECT COALESCE(MAX(length), 0) AS best_streak FROM streaks
                """,
                (STREAK_TIMEZONE, user_id),
            )
            best_streak_row = await cur.fetchone()

            await cur.execute(
                """
                SELECT EXTRACT(EPOCH FROM AVG(rse.resolved_at - rse.created_at))::int AS avg_seconds
                FROM review_session_entries rse
                JOIN review_sessions rs ON rs.id = rse.review_session_id
                WHERE rs.user_id = %s
                  AND rse.status = 'resolved'
                  AND rse.resolved_at IS NOT NULL
                  AND rse.resolved_at >= NOW() - INTERVAL '30 days'
                """,
                (user_id,),
            )
            avg_row = await cur.fetchone()

    return {
        "today_resolved": stats.today_resolved,  # type: ignore[union-attr]
        "streak": streak_row.length if streak_row else 0,  # type: ignore[union-attr]
        "all_time_resolved": stats.all_time_resolved,  # type: ignore[union-attr]
        "available_count": available.available_count,  # type: ignore[union-attr]
        "claimed_count": claimed.claimed_count,  # type: ignore[union-attr]
        "daily_counts": [{"date": row.date, "count": row.count} for row in daily_rows],  # type: ignore[union-attr]
        "current_date": stats.current_date.isoformat(),  # type: ignore[union-attr]
        "best_streak": best_streak_row.best_streak,  # type: ignore[union-attr]
        "avg_seconds_per_review": avg_row.avg_seconds,  # type: ignore[union-attr]
    }
