from datetime import timedelta

from database.database import get_pool
from database.review_sessions import SESSION_IDLE_TIMEOUT_MINUTES

# Review session entry lifecycle — one place for how a single entry moves between
# statuses. Selection (which PR to offer next) lives in review_session_navigation.py.
#
#   claimed ──pass_entry──────────────▶ passed
#      │
#      ├──save_entries_for_request─────▶ saved      (committed to the branch, not published)
#      │                                     │
#      └──resolve_entries_for_request──▶ resolved   (credit signal for stats/streak/goal)
#                                        ▲
#              a saved card that is later published promotes to resolved
#
#   non-resolved entries are purged (DELETEd) in three places:
#     • purge_stale_idle_sessions()                      — scheduled sweep (here)
#     • review_sessions._purge_session_queue(cur, …)     — session end/reset (in caller's txn)
#     • review_session_navigation._cleanup_stale_entries — pre-allocate (in navigate's txn)
#   The latter two are cursor-bound: they must run inside their caller's transaction.
#
#   'saved' is exempt from _cleanup_stale_entries only. That sweep keys on the
#   entry's own created_at, so it would release a saved card out from under a
#   reviewer whose session is still live. The other two purges key on session
#   state, which is the signal a save is meant to be held against.


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


async def save_entries_for_request(changeset_id: str) -> None:
    """Mark the claimed entry holding this request as saved. A no-op if it is already saved."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'saved'
                WHERE %s = ANY(changeset_ids) AND status = 'claimed'
                """,
                (changeset_id,),
            )


async def resolve_entries_for_request(changeset_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'resolved', resolved_at = NOW()
                WHERE %s = ANY(changeset_ids) AND status != 'resolved'
                """,
                (changeset_id,),
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
