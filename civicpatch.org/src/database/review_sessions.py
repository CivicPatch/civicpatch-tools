import logging
from enum import StrEnum
from typing import Any
from database.database import get_pool
from psycopg.rows import namedtuple_row
from shared.utils.date_utils import STREAK_TIMEZONE

logger = logging.getLogger(__name__)


class ReviewSessionEntryStatus(StrEnum):
    CLAIMED = "claimed"
    PASSED = "passed"
    RESOLVED = "resolved"


class AdvanceDoneReason(StrEnum):
    GOAL_REACHED = "goal_reached"
    NO_MORE_CARDS = "no_more_cards"


async def create_or_get_review_session(
    user_id: str,
    state_code: str,
    daily_goal: int | None = None,
) -> dict[str, Any]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=namedtuple_row) as cur:
            if daily_goal is None:
                await cur.execute(
                    """
                    SELECT daily_goal FROM review_sessions
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = await cur.fetchone()
                daily_goal = row.daily_goal if row else 10  # type: ignore[union-attr]

            # Clear non-resolved entries so every "start review" is a fresh slate
            await cur.execute(
                """
                DELETE FROM review_session_entries
                WHERE review_session_id IN (
                    SELECT id FROM review_sessions
                    WHERE user_id = %s AND state_code = %s
                )
                AND status NOT IN ('resolved')
                """,
                (user_id, state_code),
            )

            await cur.execute(
                """
                INSERT INTO review_sessions
                    (user_id, state_code, daily_goal)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, state_code)
                    DO UPDATE SET daily_goal = EXCLUDED.daily_goal
                RETURNING id, state_code, daily_goal, created_at
                """,
                (user_id, state_code, daily_goal),
            )
            row = await cur.fetchone()

    return {
        "id": str(row.id),  # type: ignore[union-attr]
        "state_code": row.state_code,  # type: ignore[union-attr]
        "daily_goal": row.daily_goal,  # type: ignore[union-attr]
        "created_at": row.created_at.isoformat(),  # type: ignore[union-attr]
    }


async def _find_next_cards(cur, review_session_id: str, state_code: str, limit: int = 1):
    await cur.execute(
        """
        WITH
        cleanup AS (
            DELETE FROM review_session_entries
            WHERE review_session_id IN (
                SELECT id FROM review_sessions
                WHERE DATE(created_at) = CURRENT_DATE AND id != %s
            )
            AND status NOT IN ('resolved')
            AND created_at < NOW() - INTERVAL '30 minutes'
        ),
        done AS (
            SELECT jurisdiction_ocdid FROM review_session_entries
            WHERE review_session_id = %s AND status IN ('resolved', 'passed')
        ),
        claimed AS (
            SELECT rse.jurisdiction_ocdid
            FROM review_session_entries rse
            JOIN review_sessions rs ON rs.id = rse.review_session_id
            WHERE rse.status = 'claimed'
              AND DATE(rs.created_at) = CURRENT_DATE
              AND rs.id != %s
        ),
        reclaimed AS (
            SELECT jurisdiction_ocdid FROM review_session_entries
            WHERE review_session_id = %s AND status = 'claimed'
        )
        SELECT j.request_id::text,
               r.jurisdiction_ocdid AS jurisdiction_ocdid
        FROM pipeline_runs j
        JOIN requests r ON r.id = j.request_id
        JOIN pull_requests pr ON pr.request_id = j.request_id
        WHERE pr.status = 'open'
          AND r.jurisdiction_ocdid LIKE %s
          AND NOT EXISTS (
              SELECT 1 FROM done
              WHERE done.jurisdiction_ocdid = r.jurisdiction_ocdid
          )
          AND NOT EXISTS (
              SELECT 1 FROM claimed
              WHERE claimed.jurisdiction_ocdid = r.jurisdiction_ocdid
          )
        ORDER BY
            (r.jurisdiction_ocdid IN (SELECT jurisdiction_ocdid FROM reclaimed)) ASC,
            jsonb_array_length(r.review_json->'issues') DESC NULLS LAST,
            pr.created_at DESC
        LIMIT %s
        """,
        (review_session_id, review_session_id, review_session_id, review_session_id, f"%state:{state_code}%", limit),
    )
    return await cur.fetchall()


async def pass_current_entry(review_session_id: str, entry_number: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'passed'
                WHERE review_session_id = %s AND entry_number = %s AND status = 'claimed'
                """,
                (review_session_id, entry_number),
            )


async def pause_review_session(review_session_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM review_session_entries
                WHERE review_session_id = %s AND status NOT IN ('resolved')
                """,
                (review_session_id,),
            )


async def navigate_to_entry(
    review_session_id: str,
    entry_number: int,
) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=namedtuple_row) as cur:
            await cur.execute(
                "SELECT state_code, daily_goal FROM review_sessions WHERE id = %s FOR UPDATE",
                (review_session_id,),
            )
            session_row = await cur.fetchone()
            if not session_row:
                return None

            # Try to find an existing entry at the requested position (claimed or passed)
            await cur.execute(
                """
                SELECT id, request_ids, jurisdiction_ocdid
                FROM review_session_entries
                WHERE review_session_id = %s
                  AND entry_number = %s
                  AND status IN ('claimed', 'passed')
                """,
                (review_session_id, entry_number),
            )
            existing = await cur.fetchone()

            if existing:
                request_id = existing.request_ids[0]  # type: ignore[union-attr]
                jurisdiction_ocdid = existing.jurisdiction_ocdid  # type: ignore[union-attr]

                # has_more: next slot already exists, or new cards are available
                await cur.execute(
                    """
                    SELECT 1 FROM review_session_entries
                    WHERE review_session_id = %s AND entry_number = %s AND status = 'claimed'
                    """,
                    (review_session_id, entry_number + 1),
                )
                has_more = (await cur.fetchone()) is not None
                if not has_more:
                    peek = await _find_next_cards(cur, review_session_id, session_row.state_code, limit=1)  # type: ignore[union-attr]
                    has_more = len(peek) > 0
            else:
                # Frontier: check goal, then allocate the next card at this position
                await cur.execute(
                    """
                    SELECT COUNT(*) FILTER (
                        WHERE status = 'resolved'
                          AND (created_at AT TIME ZONE %s)::date = (NOW() AT TIME ZONE %s)::date
                    ) AS resolved
                    FROM review_session_entries
                    WHERE review_session_id = %s
                    """,
                    (STREAK_TIMEZONE, STREAK_TIMEZONE, review_session_id),
                )
                counts_row = await cur.fetchone()
                if counts_row.resolved >= session_row.daily_goal:  # type: ignore[union-attr]
                    return {"done": AdvanceDoneReason.GOAL_REACHED}

                rows = await _find_next_cards(cur, review_session_id, session_row.state_code, limit=2)  # type: ignore[union-attr]
                if not rows:
                    return {"done": AdvanceDoneReason.NO_MORE_CARDS}

                next_card = rows[0]
                await cur.execute(
                    """
                    INSERT INTO review_session_entries
                        (review_session_id, request_ids, jurisdiction_ocdid, status, entry_number)
                    VALUES (%s, %s, %s, 'claimed', %s)
                    """,
                    (review_session_id, [next_card.request_id], next_card.jurisdiction_ocdid, entry_number),  # type: ignore[union-attr]
                )
                request_id = next_card.request_id
                jurisdiction_ocdid = next_card.jurisdiction_ocdid
                has_more = len(rows) > 1

            await cur.execute(
                """
                SELECT COUNT(*) FILTER (
                    WHERE status = 'resolved'
                      AND (created_at AT TIME ZONE %s)::date = (NOW() AT TIME ZONE %s)::date
                ) AS resolved_count
                FROM review_session_entries
                WHERE review_session_id = %s
                """,
                (STREAK_TIMEZONE, STREAK_TIMEZONE, review_session_id),
            )
            counts = await cur.fetchone()

            await cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM review_session_entries
                    WHERE review_session_id = %s
                      AND entry_number < %s
                      AND status = 'claimed'
                ) AS has_prev
                """,
                (review_session_id, entry_number),
            )
            prev_row = await cur.fetchone()

    return {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "entry_number": entry_number,
        "resolved_count": counts.resolved_count,  # type: ignore[union-attr]
        "has_more": has_more,
        "has_prev": prev_row.has_prev,  # type: ignore[union-attr]
    }


async def resolve_review_session_entries_by_request_id(request_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'resolved', resolved_at = NOW()
                WHERE %s = ANY(request_ids) AND status != 'resolved'
                """,
                (request_id,),
            )


async def resolve_review_session_entries_by_pr_number(pr_number: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'resolved', resolved_at = NOW()
                WHERE EXISTS (
                    SELECT 1 FROM pipeline_runs j
                    JOIN requests r ON r.id = j.request_id
                    JOIN pull_requests pr ON pr.request_id = r.id
                    WHERE pr.url LIKE %s
                      AND j.request_id::text = ANY(review_session_entries.request_ids)
                )
                AND status != 'resolved'
                """,
                (f"%/pull/{pr_number}",),
            )


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
                """
                SELECT COUNT(*) AS available_count
                FROM pipeline_runs j
                JOIN requests r ON r.id = j.request_id
                JOIN pull_requests pr ON pr.request_id = r.id
                WHERE pr.status = 'open'
                  AND r.jurisdiction_ocdid LIKE %s
                """,
                (f"%state:{state_code}%",),
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
