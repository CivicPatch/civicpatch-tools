from datetime import timedelta

from database.database import get_pool
from database.review_sessions import SESSION_IDLE_TIMEOUT_MINUTES

# Review session entry lifecycle — one place for how a single entry moves between
# statuses. Selection (which PR to offer next) lives in review_session_navigation.py.
#
#   claimed ──pass_entry──────────────▶ passed
#      │
#      └──resolve_entries_for_request──▶ resolved   (credit: appends reviewed_request_ids)
#
#   non-resolved entries are purged (DELETEd) in three places:
#     • purge_stale_idle_sessions()                      — scheduled sweep (here)
#     • review_sessions._purge_session_queue(cur, …)     — session end/reset (in caller's txn)
#     • review_session_navigation._cleanup_stale_entries — pre-allocate (in navigate's txn)
#   The latter two are cursor-bound: they must run inside their caller's transaction.


async def pass_entry(review_session_id: str, entry_number: int) -> None:
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


async def resolve_entries_for_request(request_id: str) -> None:
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
            # Append the resolved request_id to the session's reviewed list so the
            # allocator won't re-serve it this session.
            await cur.execute(
                """
                UPDATE review_sessions rs
                SET reviewed_request_ids = array_append(reviewed_request_ids, %s)
                WHERE NOT (%s = ANY(COALESCE(rs.reviewed_request_ids, ARRAY[]::text[])))
                  AND EXISTS (
                      SELECT 1 FROM review_session_entries rse
                      WHERE rse.review_session_id = rs.id
                        AND %s = ANY(rse.request_ids)
                  )
                """,
                (request_id, request_id, request_id),
            )


async def purge_stale_idle_sessions() -> dict:
    """
    Periodic cleanup for the Temporal scheduler.

    Deletes non-resolved entries from sessions whose updated_at is past the idle
    timeout. The trigger on review_sessions keeps updated_at current on every write,
    so only genuinely abandoned sessions are affected.

    Returns the number of entries deleted.
    """
    timeout = timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM review_session_entries
                USING review_sessions
                WHERE review_session_entries.review_session_id = review_sessions.id
                  AND review_session_entries.status NOT IN ('resolved')
                  AND review_sessions.updated_at < NOW() - %s
                """,
                (timeout,),
            )
            entries_deleted = cur.rowcount

    return {"entries_deleted": entries_deleted}
