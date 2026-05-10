import logging
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
from database.database import get_pool
from psycopg.rows import namedtuple_row
from shared.utils.date_utils import STREAK_TIMEZONE

logger = logging.getLogger(__name__)

SESSION_IDLE_TIMEOUT_MINUTES = 30


class ReviewSessionStatus(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"
    COMPLETE = "complete"


class ReviewSessionEntryStatus(StrEnum):
    CLAIMED = "claimed"
    PASSED = "passed"
    RESOLVED = "resolved"


class AdvanceDoneReason(StrEnum):
    GOAL_REACHED = "goal_reached"
    NO_MORE_CARDS = "no_more_cards"


async def get_active_review_session(user_id: str) -> dict[str, Any] | None:
    """
    Returns the most recently active session for this user if it is ACTIVE
    and was updated within the idle timeout window. Returns None otherwise.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=namedtuple_row) as cur:
            await cur.execute(
                """
                SELECT rs.id AS session_id,
                       rs.state_code,
                       rs.daily_goal,
                       rs.current_entry_number,
                       ARRAY_AGG(rse.entry_number ORDER BY rse.entry_number)
                           FILTER (WHERE rse.status = 'resolved') AS resolved_entry_numbers,
                       ARRAY(
                           SELECT pr.pr_number
                           FROM review_session_entries rse2
                           JOIN pull_requests pr ON pr.request_id::text = rse2.request_ids[1]
                           WHERE rse2.review_session_id = rs.id
                       ) AS session_pull_request_numbers
                FROM review_sessions rs
                LEFT JOIN review_session_entries rse ON rse.review_session_id = rs.id
                WHERE rs.user_id = %s
                  AND rs.status = %s
                  AND rs.status_updated_at > NOW() - %s
                GROUP BY rs.id, rs.state_code, rs.daily_goal, rs.current_entry_number
                ORDER BY rs.status_updated_at DESC
                LIMIT 1
                """,
                (user_id, ReviewSessionStatus.ACTIVE, timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)),
            )
            row = await cur.fetchone()

    if not row:
        return None
    return {
        "session_id": str(row.session_id),  # type: ignore[union-attr]
        "state_code": row.state_code,  # type: ignore[union-attr]
        "daily_goal": row.daily_goal,  # type: ignore[union-attr]
        "current_entry_number": row.current_entry_number,  # type: ignore[union-attr]
        "resolved_entry_numbers": row.resolved_entry_numbers or [],  # type: ignore[union-attr]
        "session_pull_request_numbers": row.session_pull_request_numbers or [],  # type: ignore[union-attr]
    }


async def _purge_session_queue(cur, review_session_id: str) -> None:
    await cur.execute(
        """
        DELETE FROM review_session_entries
        WHERE review_session_id = %s AND status NOT IN ('resolved')
        """,
        (review_session_id,),
    )


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

            # Read the current session status directly — no subquery needed.
            # ACTIVE + recent → resume; anything else → purge and start fresh.
            await cur.execute(
                """
                SELECT status, status_updated_at
                FROM review_sessions
                WHERE user_id = %s AND state_code = %s
                """,
                (user_id, state_code),
            )
            existing = await cur.fetchone()
            idle_cutoff = datetime.now(timezone.utc) - timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)
            is_active = (
                existing is not None
                and existing.status == ReviewSessionStatus.ACTIVE  # type: ignore[union-attr]
                and existing.status_updated_at is not None  # type: ignore[union-attr]
                and existing.status_updated_at > idle_cutoff  # type: ignore[union-attr]
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

            if not is_active:
                await _purge_session_queue(cur, str(row.id))  # type: ignore[union-attr]
                await cur.execute(
                    """
                    UPDATE review_sessions SET status = %s, status_updated_at = NOW()
                    WHERE id = %s
                    """,
                    (ReviewSessionStatus.IDLE, str(row.id)),  # type: ignore[union-attr]
                )

            await cur.execute(
                """
                SELECT COALESCE(MAX(entry_number), 0) + 1 AS next_entry_number
                FROM review_session_entries
                WHERE review_session_id = %s
                """,
                (str(row.id),),  # type: ignore[union-attr]
            )
            next_entry_row = await cur.fetchone()

    return {
        "id": str(row.id),  # type: ignore[union-attr]
        "state_code": row.state_code,  # type: ignore[union-attr]
        "daily_goal": row.daily_goal,  # type: ignore[union-attr]
        "created_at": row.created_at.isoformat(),  # type: ignore[union-attr]
        "next_entry_number": next_entry_row.next_entry_number if next_entry_row else 1,  # type: ignore[union-attr]
    }



async def end_review_session(review_session_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await _purge_session_queue(cur, review_session_id)
            await cur.execute(
                """
                UPDATE review_sessions
                SET status = %s, status_updated_at = NOW(), current_entry_number = 1,
                    reviewed_ocdids = '{}'
                WHERE id = %s
                """,
                (ReviewSessionStatus.IDLE, review_session_id),
            )
