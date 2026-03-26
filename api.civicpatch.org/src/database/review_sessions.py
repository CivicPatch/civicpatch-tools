import logging
from datetime import date
from enum import StrEnum
from typing import Any
from database.database import get_pool
from psycopg.rows import namedtuple_row

logger = logging.getLogger(__name__)


class ReviewSessionEntryStatus(StrEnum):
    CLAIMED = "claimed"
    PASSED = "passed"
    RESOLVED = "resolved"


class AdvanceDoneReason(StrEnum):
    GOAL_REACHED = "goal_reached"
    NO_MORE_CARDS = "no_more_cards"


async def create_or_get_review_session(
    provider: str,
    provider_user_id: str,
    session_date: date,
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
                    WHERE provider = %s AND provider_user_id = %s
                    ORDER BY session_date DESC
                    LIMIT 1
                    """,
                    (provider, provider_user_id),
                )
                row = await cur.fetchone()
                daily_goal = row.daily_goal if row else 10

            await cur.execute(
                """
                INSERT INTO review_sessions
                    (provider, provider_user_id, session_date, state_code, daily_goal)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (provider, provider_user_id, session_date, state_code)
                    DO UPDATE SET daily_goal = EXCLUDED.daily_goal
                RETURNING id, state_code, daily_goal, session_date, created_at
                """,
                (provider, provider_user_id, session_date, state_code, daily_goal),
            )
            row = await cur.fetchone()

    return {
        "id": str(row.id),
        "state_code": row.state_code,
        "daily_goal": row.daily_goal,
        "session_date": row.session_date.isoformat(),
        "created_at": row.created_at.isoformat(),
    }


# TODO: rename to get_current_session_with_current_entry
async def get_today_session_with_current_entry(
    provider: str,
    provider_user_id: str,
    state_code: str,
) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=namedtuple_row) as cur:
            await cur.execute(
                """
                SELECT rs.id, rs.state_code, rs.daily_goal, rs.session_date, rs.created_at,
                       (
                           SELECT array_agg(entry_number)
                           FROM review_session_entries
                           WHERE review_session_id = rs.id AND status = 'passed'
                       ) AS passed_entry_numbers
                FROM review_sessions rs
                WHERE rs.provider = %s
                  AND rs.provider_user_id = %s
                  AND rs.session_date = CURRENT_DATE
                  AND rs.state_code = %s
                LIMIT 1
                """,
                (provider, provider_user_id, state_code),
            )
            row = await cur.fetchone()
            if not row:
                return None

    session = {
        "id": str(row.id),
        "state_code": row.state_code,
        "daily_goal": row.daily_goal,
        "session_date": row.session_date.isoformat(),
        "created_at": row.created_at.isoformat(),
    }

    return {
        "session": session,
        "passed_entry_numbers": row.passed_entry_numbers or [],
    }


async def _find_next_cards(cur, review_session_id: str, state_code: str, limit: int = 1):
    await cur.execute(
        """
        WITH
        done AS (
            SELECT jurisdiction_ocdid FROM review_session_entries
            WHERE review_session_id = %s AND status IN ('resolved', 'passed')
        ),
        claimed AS (
            SELECT rse.jurisdiction_ocdid
            FROM review_session_entries rse
            JOIN review_sessions rs ON rs.id = rse.review_session_id
            WHERE rse.status = 'claimed'
              AND rs.session_date = CURRENT_DATE
              AND rs.id != %s
        ),
        reclaimed AS (
            SELECT jurisdiction_ocdid FROM review_session_entries
            WHERE review_session_id = %s AND status = 'claimed'
        )
        SELECT j.request_id,
               j.arguments_json->>'jurisdiction_ocdid' AS jurisdiction_ocdid
        FROM jobs j
        WHERE j.pull_request_status = 'open'
          AND j.arguments_json->>'jurisdiction_ocdid' LIKE %s
          AND NOT EXISTS (
              SELECT 1 FROM done
              WHERE done.jurisdiction_ocdid = j.arguments_json->>'jurisdiction_ocdid'
          )
          AND NOT EXISTS (
              SELECT 1 FROM claimed
              WHERE claimed.jurisdiction_ocdid = j.arguments_json->>'jurisdiction_ocdid'
          )
        ORDER BY
            (j.arguments_json->>'jurisdiction_ocdid' IN (SELECT jurisdiction_ocdid FROM reclaimed)) ASC,
            (j.pull_request_review_state = 'changes_requested') DESC,
            j.created_at DESC
        LIMIT %s
        """,
        (review_session_id, review_session_id, review_session_id, f"%state:{state_code}%", limit),
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
                SELECT id, request_id, jurisdiction_ocdid
                FROM review_session_entries
                WHERE review_session_id = %s
                  AND entry_number = %s
                  AND status IN ('claimed', 'passed')
                """,
                (review_session_id, entry_number),
            )
            existing = await cur.fetchone()

            if existing:
                request_id = existing.request_id
                jurisdiction_ocdid = existing.jurisdiction_ocdid

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
                    peek = await _find_next_cards(cur, review_session_id, session_row.state_code, limit=1)
                    has_more = len(peek) > 0
            else:
                # Frontier: check goal, then allocate the next card at this position
                await cur.execute(
                    """
                    SELECT COUNT(*) FILTER (WHERE status = 'resolved') AS resolved
                    FROM review_session_entries
                    WHERE review_session_id = %s
                    """,
                    (review_session_id,),
                )
                counts_row = await cur.fetchone()
                if counts_row.resolved >= session_row.daily_goal:
                    return {"done": AdvanceDoneReason.GOAL_REACHED}

                rows = await _find_next_cards(cur, review_session_id, session_row.state_code, limit=2)
                if not rows:
                    return {"done": AdvanceDoneReason.NO_MORE_CARDS}

                next_card = rows[0]
                await cur.execute(
                    """
                    INSERT INTO review_session_entries
                        (review_session_id, request_id, jurisdiction_ocdid, status, entry_number)
                    VALUES (%s, %s, %s, 'claimed', %s)
                    """,
                    (review_session_id, next_card.request_id, next_card.jurisdiction_ocdid, entry_number),
                )
                request_id = next_card.request_id
                jurisdiction_ocdid = next_card.jurisdiction_ocdid
                has_more = len(rows) > 1

            await cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_count
                FROM review_session_entries
                WHERE review_session_id = %s
                """,
                (review_session_id,),
            )
            counts = await cur.fetchone()

    return {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "entry_number": entry_number,
        "resolved_count": counts.resolved_count,
        "has_more": has_more,
    }


async def resolve_review_session_entries_by_request_id(request_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'resolved'
                WHERE request_id = %s AND status != 'resolved'
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
                SET status = 'resolved'
                WHERE request_id IN (
                    SELECT request_id FROM jobs
                    WHERE pull_request_url LIKE %s
                )
                AND status != 'resolved'
                """,
                (f"%/pull/{pr_number}",),
            )


async def get_review_stats(
    provider: str,
    provider_user_id: str,
    state_code: str,
) -> dict[str, Any]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=namedtuple_row) as cur:
            await cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE rs.session_date = CURRENT_DATE) AS today_resolved,
                    COUNT(*) AS all_time_resolved
                FROM review_session_entries rse
                JOIN review_sessions rs ON rs.id = rse.review_session_id
                WHERE rs.provider = %s AND rs.provider_user_id = %s
                  AND rse.status = 'resolved'
                """,
                (provider, provider_user_id),
            )
            stats = await cur.fetchone()

            await cur.execute(
                """
                WITH daily AS (
                    SELECT DISTINCT rs.session_date
                    FROM review_session_entries rse
                    JOIN review_sessions rs ON rs.id = rse.review_session_id
                    WHERE rs.provider = %s AND rs.provider_user_id = %s
                      AND rse.status = 'resolved'
                      AND rs.session_date >= CURRENT_DATE - INTERVAL '365 days'
                ),
                grouped AS (
                    SELECT session_date,
                           session_date - (ROW_NUMBER() OVER (ORDER BY session_date))::int AS grp
                    FROM daily
                ),
                streaks AS (
                    SELECT COUNT(*) AS length, MAX(session_date) AS last_day
                    FROM grouped
                    GROUP BY grp
                )
                SELECT length FROM streaks
                WHERE last_day >= CURRENT_DATE - 1
                ORDER BY last_day DESC
                LIMIT 1
                """,
                (provider, provider_user_id),
            )
            streak_row = await cur.fetchone()

            await cur.execute(
                """
                SELECT COUNT(DISTINCT j.arguments_json->>'jurisdiction_ocdid') AS available_count
                FROM jobs j
                WHERE j.pull_request_status = 'open'
                  AND j.arguments_json->>'jurisdiction_ocdid' LIKE %s
                """,
                (f"%state:{state_code}%",),
            )
            available = await cur.fetchone()

    return {
        "today_resolved": stats.today_resolved,
        "streak": streak_row.length if streak_row else 0,
        "all_time_resolved": stats.all_time_resolved,
        "available_count": available.available_count,
    }
