import logging
from typing import Any
from database.database import get_pool
from psycopg.rows import namedtuple_row
logger = logging.getLogger(__name__)

SESSION_IDLE_TIMEOUT_MINUTES = 30


class ReviewSessionEntryStatus(str):
    CLAIMED = "claimed"
    PASSED = "passed"
    SAVED = "saved"
    RESOLVED = "resolved"


class AdvanceDoneReason(str):
    GOAL_REACHED = "goal_reached"
    NO_MORE_CARDS = "no_more_cards"


async def get_active_review_session(user_id: str, state_code: str) -> dict[str, Any] | None:
    """
    Returns the (user, state) session if it has been written to within the idle
    timeout window. updated_at is bumped automatically on every write via trigger,
    so any navigation activity (forward or back) keeps the session alive.
    Returns None if the session is stale or does not exist for this state.
    The schema enforces at most one active session per (user_id, state_code).
    """
    from datetime import timedelta
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
                       -- Ordered, so position n is entry number n + 1: that is how a caller
                       -- turns "open this request" into "go to this entry".
                       ARRAY(
                           SELECT rse2.changeset_ids[1]
                           FROM review_session_entries rse2
                           WHERE rse2.review_session_id = rs.id
                           ORDER BY rse2.entry_number
                       ) AS session_changeset_ids
                FROM review_sessions rs
                LEFT JOIN review_session_entries rse ON rse.review_session_id = rs.id
                WHERE rs.user_id = %s
                  AND rs.state_code = %s
                  AND rs.ended_at IS NULL
                  AND rs.updated_at > NOW() - %s
                  AND EXISTS (
                      SELECT 1 FROM review_session_entries rse2
                      WHERE rse2.review_session_id = rs.id
                        AND rse2.status = 'claimed'
                  )
                GROUP BY rs.id, rs.state_code, rs.daily_goal, rs.current_entry_number
                """,
                (user_id, state_code, timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)),
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
        "session_changeset_ids": row.session_changeset_ids or [],  # type: ignore[union-attr]
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
    from datetime import timedelta
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

            await cur.execute(
                """
                SELECT id,
                       (updated_at > NOW() - %s) AS is_active
                FROM review_sessions
                WHERE user_id = %s AND state_code = %s
                  AND ended_at IS NULL
                """,
                (timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES), user_id, state_code),
            )
            existing = await cur.fetchone()

            if existing and existing.is_active:  # type: ignore[union-attr]
                await cur.execute(
                    """
                    UPDATE review_sessions
                    SET daily_goal = %s
                    WHERE id = %s
                    RETURNING id, state_code, daily_goal, created_at
                    """,
                    (daily_goal, str(existing.id)),  # type: ignore[union-attr]
                )
                row = await cur.fetchone()
            else:
                if existing:
                    await _purge_session_queue(cur, str(existing.id))  # type: ignore[union-attr]
                    await cur.execute(
                        """
                        UPDATE review_sessions
                        SET ended_at = NOW()
                        WHERE id = %s
                        """,
                        (str(existing.id),),  # type: ignore[union-attr]
                    )

                await cur.execute(
                    """
                    INSERT INTO review_sessions (user_id, state_code, daily_goal)
                    VALUES (%s, %s, %s)
                    RETURNING id, state_code, daily_goal, created_at
                    """,
                    (user_id, state_code, daily_goal),
                )
                row = await cur.fetchone()

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
                SET ended_at = NOW()
                WHERE id = %s AND ended_at IS NULL
                """,
                (review_session_id,),
            )
