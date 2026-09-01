from datetime import timedelta
from typing import Any

from database.database import get_pool
from database.changesets import AVAILABLE_FOR_REVIEW
from database.review_queue import issue_priority
from database.review_sessions import (
    AdvanceDoneReason,
    ReviewSessionEntryStatus,
    SESSION_IDLE_TIMEOUT_MINUTES,
)
from psycopg.rows import namedtuple_row
from shared.utils.date_utils import STREAK_TIMEZONE


async def _cleanup_stale_entries(cur, exclude_session_id: str) -> None:
    """Delete claimed entries from any other session that have been idle past the timeout.

    The timeout check is on the entry's created_at, not the session's — an entry
    older than SESSION_IDLE_TIMEOUT_MINUTES is considered abandoned regardless of
    when its parent session was created.

    'saved' entries are exempt: because this keys on entry age rather than session
    activity, it would otherwise hand a saved card to another reviewer while the
    saving session is still live. purge_stale_idle_sessions releases those instead,
    keyed on the session's own updated_at.
    """
    await cur.execute(
        """
        DELETE FROM review_session_entries
        WHERE review_session_id IN (
            SELECT id FROM review_sessions
            WHERE id != %s
        )
        AND status NOT IN ('resolved', 'saved')
        AND created_at < NOW() - %s
        """,
        (
            exclude_session_id,
            timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),
        ),
    )


async def _session_in_progress_request_ids(cur, review_session_id: str) -> list[str]:
    """request_ids currently claimed (in progress) in this session."""
    await cur.execute(
        "SELECT DISTINCT unnest(request_ids) FROM review_session_entries WHERE review_session_id = %s AND status = 'claimed'",
        (review_session_id,),
    )
    return [r[0] for r in await cur.fetchall()]


async def _allocate_next_review(cur, state_code: str, excluded_request_ids: list, limit: int = 1):
    """
    Returns the next available open review(s) for this session.

    Excludes request_ids currently claimed (in progress) in this session so an in-flight
    card isn't re-offered, and excludes jurisdictions already claimed by any other
    session so two reviewers don't race for the same top-ranked candidate (the
    ordering below is deterministic, so without this they'd otherwise pick the same
    one almost every time). Resolved/published PRs are already out of the pool via
    AVAILABLE_FOR_REVIEW. The router's UniqueViolation retry handles the remaining
    select-then-insert race window.

    'saved' jurisdictions are held on the same footing as claimed ones: the card was
    committed to but not published, so it stays with its session until that session
    is released. The hold is not session-scoped, which is also what stops a session
    being re-offered its own saved card later in the queue.
    """
    await cur.execute(
        f"""
        SELECT r.id::text AS changeset_id,
               r.jurisdiction_ocdid AS jurisdiction_ocdid
        FROM changesets r
        WHERE {AVAILABLE_FOR_REVIEW}
          AND r.jurisdiction_ocdid LIKE %s
          AND r.id::text != ALL(%s::text[])
          AND NOT EXISTS (
              SELECT 1 FROM review_session_entries e
              WHERE e.jurisdiction_ocdid = r.jurisdiction_ocdid
                AND e.status IN ('claimed', 'saved')
          )
        ORDER BY
            {issue_priority('r.jurisdiction_ocdid')} DESC,
            r.created_at DESC
        LIMIT %s
        """,
        (
            f"ocd-jurisdiction/country:us/state:{state_code}/%",
            excluded_request_ids,
            limit,
        ),
    )
    return await cur.fetchall()


async def _navigate_to_existing_entry(cur, review_session_id: str, entry_number: int, state_code: str):
    """Re-navigate to an existing entry at any status. Returns (changeset_id, jurisdiction_ocdid, has_next) or None."""
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
            ReviewSessionEntryStatus.SAVED,
            ReviewSessionEntryStatus.RESOLVED,
        ]),
    )
    existing = await cur.fetchone()
    if not existing:
        return None

    changeset_id = existing.request_ids[0]  # type: ignore[union-attr]
    jurisdiction_ocdid = existing.jurisdiction_ocdid  # type: ignore[union-attr]

    await cur.execute(
        """
        SELECT 1 FROM review_session_entries
        WHERE review_session_id = %s AND entry_number = %s AND status = 'claimed'
        """,
        (review_session_id, entry_number + 1),
    )
    has_next = (await cur.fetchone()) is not None
    if not has_next:
        in_progress = await _session_in_progress_request_ids(cur, review_session_id)
        peek = await _allocate_next_review(cur, state_code, in_progress, limit=1)
        has_next = len(peek) > 0

    return changeset_id, jurisdiction_ocdid, has_next


async def _allocate_next_entry(cur, review_session_id: str, entry_number: int, session_row):
    """Allocate the next available card at the frontier. Returns (changeset_id, jurisdiction_ocdid, has_next) or a done dict."""
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

    # Exclude any card currently claimed in this session so an in-flight one isn't re-offered.
    in_progress = await _session_in_progress_request_ids(cur, review_session_id)
    rows = await _allocate_next_review(cur, session_row.state_code, in_progress, limit=2)  # type: ignore[union-attr]
    if not rows:
        return {"done": AdvanceDoneReason.NO_MORE_CARDS}

    next_card = rows[0]
    await cur.execute(
        """
        INSERT INTO review_session_entries
            (review_session_id, request_ids, jurisdiction_ocdid, status, entry_number)
        VALUES (%s, %s, %s, 'claimed', %s)
        """,
        (review_session_id, [next_card.changeset_id], next_card.jurisdiction_ocdid, entry_number),  # type: ignore[union-attr]
    )
    return next_card.changeset_id, next_card.jurisdiction_ocdid, len(rows) > 1  # type: ignore[union-attr]


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
                # Release any jurisdictions held by idle sessions before allocating
                await _cleanup_stale_entries(cur, review_session_id)
                result = await _allocate_next_entry(cur, review_session_id, entry_number, session_row)

            if isinstance(result, dict):
                return result

            changeset_id, jurisdiction_ocdid, has_next = result

            await cur.execute(
                """
                UPDATE review_sessions
                SET current_entry_number = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (entry_number, review_session_id),
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

            # Live count of PRs still reviewable in this state (open, not parked for merge).
            # changeset_id is the unit, so COUNT(*), not distinct jurisdictions. Published PRs
            # are already excluded by AVAILABLE_FOR_REVIEW. The authoritative progress total.
            await cur.execute(
                f"""
                SELECT COUNT(*) AS available
                FROM changesets r
                WHERE {AVAILABLE_FOR_REVIEW}
                  AND r.jurisdiction_ocdid LIKE %s
                """,
                (f"ocd-jurisdiction/country:us/state:{session_row.state_code}/%",),  # type: ignore[union-attr]
            )
            avail = await cur.fetchone()

    resolved_count = counts.resolved_count  # type: ignore[union-attr]
    daily_goal = session_row.daily_goal  # type: ignore[union-attr]
    # Session length = the goal, capped by what's actually reviewable (done +
    # still-available), and never fewer than where we already are.
    total = max(entry_number, min(daily_goal, resolved_count + avail.available))  # type: ignore[union-attr]
    # A next entry exists only if the pool can offer one AND we're not already at the end of
    # the session. total encodes the daily_goal cap that the pool-availability check ignores.
    has_next = has_next and entry_number < total

    return {
        "changeset_id": changeset_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "entry_number": entry_number,
        "resolved_count": resolved_count,
        "goal": daily_goal,
        "total": total,
        "has_next": has_next,
    }
