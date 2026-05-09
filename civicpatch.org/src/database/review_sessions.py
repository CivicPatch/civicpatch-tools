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


async def get_active_review_session(user_id: str, state_code: str) -> dict[str, Any] | None:
    """
    Returns the current session and entry position if the session is ACTIVE
    and was updated within the idle timeout window. Returns None otherwise.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=namedtuple_row) as cur:
            await cur.execute(
                """
                SELECT rs.id AS session_id,
                       rs.daily_goal,
                       COALESCE(
                           MAX(rse.entry_number) FILTER (WHERE rse.status = 'claimed'),
                           MAX(rse.entry_number) + 1,
                           1
                       ) AS current_entry_number,
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
                  AND rs.state_code = %s
                  AND rs.status = %s
                  AND rs.status_updated_at > NOW() - %s
                GROUP BY rs.id, rs.daily_goal
                """,
                (user_id, state_code, ReviewSessionStatus.ACTIVE, timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)),
            )
            row = await cur.fetchone()

    if not row:
        return None
    return {
        "session_id": str(row.session_id),  # type: ignore[union-attr]
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


async def _cleanup_stale_entries(cur, exclude_session_id: str) -> None:
    """Delete claimed/passed entries from other sessions idle past the timeout."""
    await cur.execute(
        """
        DELETE FROM review_session_entries
        WHERE review_session_id IN (
            SELECT id FROM review_sessions
            WHERE created_at >= CURRENT_DATE AND created_at < CURRENT_DATE + %s
              AND id != %s
        )
        AND status NOT IN ('resolved')
        AND created_at < NOW() - %s
        """,
        (
            timedelta(days=1),
            exclude_session_id,
            timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),
        ),
    )


async def _allocate_next_review(cur, review_session_id: str, state_code: str, limit: int = 1):
    """
    Returns the next available open review(s) for this session.

    Excludes jurisdictions already reviewed or passed in this session (done).
    Excludes jurisdictions currently claimed by another active session (claimed).
    Deprioritizes jurisdictions this session previously passed (previously_passed).
    """
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
              AND rs.created_at >= CURRENT_DATE AND rs.created_at < CURRENT_DATE + %s
              AND rs.id != %s
        ),
        previously_passed AS (
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
            (r.jurisdiction_ocdid IN (SELECT jurisdiction_ocdid FROM previously_passed)) ASC,
            jsonb_array_length(r.review_json->'issues') DESC NULLS LAST,
            pr.created_at DESC
        LIMIT %s
        """,
        (
            review_session_id,                                    # done: session entries
            timedelta(days=1),                                    # claimed: CURRENT_DATE + 1 day
            review_session_id,                                    # claimed: session id
            review_session_id,                                    # previously_passed: session entries
            f"ocd-jurisdiction/country:us/state:{state_code}/%", # jurisdiction prefix
            limit,
        ),
    )
    return await cur.fetchall()


async def _navigate_to_existing_entry(cur, review_session_id: str, entry_number: int, state_code: str):
    """Re-navigate to an existing entry at any status. Returns (request_id, jurisdiction_ocdid, has_more) or None."""
    await cur.execute(
        """
        SELECT id, request_ids, jurisdiction_ocdid
        FROM review_session_entries
        WHERE review_session_id = %s
          AND entry_number = %s
          AND status = ANY(%s)
        """,
        (review_session_id, entry_number, [
            ReviewSessionEntryStatus.CLAIMED,
            ReviewSessionEntryStatus.PASSED,
            ReviewSessionEntryStatus.RESOLVED,
        ]),
    )
    existing = await cur.fetchone()
    if not existing:
        return None

    request_id = existing.request_ids[0]  # type: ignore[union-attr]
    jurisdiction_ocdid = existing.jurisdiction_ocdid  # type: ignore[union-attr]

    await cur.execute(
        """
        SELECT 1 FROM review_session_entries
        WHERE review_session_id = %s AND entry_number = %s AND status = 'claimed'
        """,
        (review_session_id, entry_number + 1),
    )
    has_more = (await cur.fetchone()) is not None
    if not has_more:
        peek = await _allocate_next_review(cur, review_session_id, state_code, limit=1)
        has_more = len(peek) > 0

    return request_id, jurisdiction_ocdid, has_more


async def _allocate_next_entry(cur, review_session_id: str, entry_number: int, session_row):
    """Allocate the next available card at the frontier. Returns (request_id, jurisdiction_ocdid, has_more) or a done dict."""
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

    rows = await _allocate_next_review(cur, review_session_id, session_row.state_code, limit=2)  # type: ignore[union-attr]
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
    return next_card.request_id, next_card.jurisdiction_ocdid, len(rows) > 1  # type: ignore[union-attr]


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

            result = await _navigate_to_existing_entry(cur, review_session_id, entry_number, session_row.state_code)  # type: ignore[union-attr]
            if result is None:
                result = await _allocate_next_entry(cur, review_session_id, entry_number, session_row)

            if isinstance(result, dict):
                # Session is done (goal reached or no more cards) → COMPLETE
                await cur.execute(
                    """
                    UPDATE review_sessions
                    SET status = %s, status_updated_at = NOW()
                    WHERE id = %s
                    """,
                    (ReviewSessionStatus.COMPLETE, review_session_id),
                )
                return result

            request_id, jurisdiction_ocdid, has_more = result

            # A card was claimed → session is ACTIVE
            await cur.execute(
                """
                UPDATE review_sessions
                SET status = %s, status_updated_at = NOW()
                WHERE id = %s
                """,
                (ReviewSessionStatus.ACTIVE, review_session_id),
            )

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

    return {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "entry_number": entry_number,
        "resolved_count": counts.resolved_count,  # type: ignore[union-attr]
        "has_more": has_more,
    }


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


async def end_review_session(review_session_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await _purge_session_queue(cur, review_session_id)
            await cur.execute(
                """
                UPDATE review_sessions
                SET status = %s, status_updated_at = NOW()
                WHERE id = %s
                """,
                (ReviewSessionStatus.IDLE, review_session_id),
            )


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


