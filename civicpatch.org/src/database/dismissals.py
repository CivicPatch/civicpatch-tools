"""The dismissal transaction: a proposal leaving the queue without going live.

The mirror of `publications.py`, and split out of `changesets.py` 2026-09-05 to look like it.
Publishing was already a named transaction module while dismissing was three functions inside
the table module, which is why "where does a dismissal happen" was harder to answer than the
same question about a publish. They are the same kind of thing.

Not a failure: a dismissed changeset keeps its evidence, it just never published.
"""

import logging
from datetime import timedelta

from core.changeset_lifecycle import ChangesetEvent, states_accepting
from database.change_logs import record_dismissal
from database.changeset_predicates import HELD_BY_REVIEWER, SWEEPABLE
from database.database import get_pool
from database.review_sessions import SESSION_IDLE_TIMEOUT_MINUTES
from database.users import SYSTEM_USER_ID
from shared.utils.statuses import DismissalReason

logger = logging.getLogger(__name__)

# Which rows are in which state, in SQL. The Python side of this is
# `core.changeset_lifecycle`; this is the same fact where the UPDATE can use it.
# "This changeset's run, if it had one, finished with a roster." One definition, because both
# halves of the lifecycle guard need it: a dismissal reason may only leave certain states, and
# `publications._refuse_if_not_publishable` asks the same question from the other side.
async def mark_dismissed(
    cur,
    changeset_ids: list[str],
    reason: DismissalReason,
    resolved_by_user_id: str | None = None,
) -> list[tuple[str, str]]:
    """The one writer for a dismissal. Returns the (id, jurisdiction) pairs that transitioned.

    Guarded in the statement, not by reading first: a reviewer may be publishing this very
    changeset, and losing that race must not overwrite their decision.

    One guard, since a changeset is only minted by a run that succeeded — there is no longer a
    failed-run changeset to keep a person from mislabelling.
    """
    if not changeset_ids:
        return []
    # The machine decides which states this dismissal may leave; the statement applies it.
    # `changesets.changeset_state` is the generated column, so this is one atomic read-and-write —
    # first, so nothing can lose the race to a concurrent publish.
    await cur.execute(
        """
        UPDATE changesets
           SET dismissed_at = now(),
               dismissed_reason = %s,
               resolved_by_user_id = COALESCE(%s, resolved_by_user_id, %s)
         WHERE changesets.id::text = ANY(%s)
           AND changesets.changeset_state = ANY(%s)
        RETURNING changesets.id::text, changesets.jurisdiction_ocdid
        """,
        (
            reason,
            resolved_by_user_id,
            SYSTEM_USER_ID,
            changeset_ids,
            list(states_accepting(ChangesetEvent.DISMISSED)),
        ),
    )
    dismissed = await cur.fetchall()
    for changeset_id, jurisdiction_ocdid in dismissed:
        await record_dismissal(
            cur, changeset_id, jurisdiction_ocdid, resolved_by_user_id, reason
        )
    return [(row[0], row[1]) for row in dismissed]


async def dismiss_superseded_by(
    cur, changeset_id: str, jurisdiction_ocdid: str, updated_at
) -> list[str]:
    """Dismiss the cards this publish just made pointless, in the publishing transaction.

    `_refuse_if_superseded` makes a stale card unpublishable; this stops it being offered at
    all. The sweep still runs — it catches two *pending* scrapes, which have no publish to hang
    off, and re-checks holds as they expire.
    """
    # Selection here, marking in `mark_dismissed`. Splitting them is safe inside this
    # transaction because that UPDATE re-checks the same guards, so a row a reviewer takes
    # between the two statements is skipped rather than overwritten.
    await cur.execute(
        f"""
        SELECT changesets.id::text FROM changesets
         WHERE changesets.jurisdiction_ocdid = %s
           AND changesets.id::text <> %s
           AND changesets.updated_at IS NOT NULL
           AND changesets.updated_at < %s
           AND {SWEEPABLE} AND NOT {HELD_BY_REVIEWER}
        """,
        (
            jurisdiction_ocdid,
            changeset_id,
            updated_at,
            timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),
        ),
    )
    stale = [row[0] for row in await cur.fetchall()]
    dismissed = await mark_dismissed(cur, stale, DismissalReason.SUPERSEDED)
    return [row[0] for row in dismissed]


async def supersede_stacked_changesets() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            WITH candidates AS (
                SELECT changesets.id, changesets.jurisdiction_ocdid, changesets.updated_at
                FROM changesets
                WHERE {SWEEPABLE} AND NOT {HELD_BY_REVIEWER}
                  AND changesets.updated_at IS NOT NULL
            ),
            supersedors AS (
                SELECT jurisdiction_ocdid, updated_at FROM candidates
                UNION ALL
                SELECT changesets.jurisdiction_ocdid, changesets.updated_at
                FROM changesets
                WHERE changesets.published_at IS NOT NULL AND changesets.updated_at IS NOT NULL
            )
            SELECT older.id::text
              FROM candidates older
             WHERE EXISTS (
                 SELECT 1 FROM supersedors newer
                 WHERE newer.jurisdiction_ocdid = older.jurisdiction_ocdid
                   AND newer.updated_at > older.updated_at
             )
            """,
            (timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),),
        )
        stale = [row[0] for row in await cur.fetchall()]
        dismissed = await mark_dismissed(cur, stale, DismissalReason.SUPERSEDED)
        await conn.commit()
        return [row[0] for row in dismissed]
