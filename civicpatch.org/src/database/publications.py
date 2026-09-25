"""The publish transaction: everything that becomes true when a scrape goes live.

One connection, one transaction. Publishing marks the changeset published and then rebuilds
the jurisdiction's projection from the facts: `load_facts` -> `derive_roster` -> the writer.
Nothing is patched and nothing is closed, because the roster is a derivation of every live
fact, not of this changeset's rows — which is why publishing a changeset that read one
organization cannot retire anyone in another.

Nothing here reads open-data.
"""

import logging

import database.dismissals as dismissals_db
from core.sinks.open_data_commit import ChangesetAttribution
from database import projection
from database.activity import record_change
from database.changeset_predicates import OPEN_REVIEW_EDIT, PUBLISHED
from database.changesets import get_updated_at
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.activity import Change
from shared.utils.statuses import (
    ActivityType,
    DismissalReason,
)

logger = logging.getLogger(__name__)


async def record_change_url(changeset_id: str, url: str) -> None:
    """Where this request's data landed in open-data. Written after the commit, not with the
    publish, because the write is queued and retried — the publish is already a fact by then.

    One url per changeset, and a hand edit mints its own — so each edit keeps the commit it
    landed in without anything per-log.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET change_url = %s WHERE id = %s", (url, changeset_id)
        )


async def publish_attributions(
    changeset_ids: list[str],
) -> dict[str, ChangesetAttribution]:
    """Who published each of these, and from which batch. Unpublished ones are left out: the
    sweep's feed also carries imports and runs that are still open or were dismissed."""
    if not changeset_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT changesets.id::text, changesets.kind, users.username,
                   changesets.batch_id::text
            FROM changesets
            LEFT JOIN users ON users.id = changesets.resolved_by_user_id
            WHERE changesets.id::text = ANY(%s) AND {PUBLISHED}
            """,
            (changeset_ids,),
        )
        rows = await cur.fetchall()
    return {
        changeset_id: ChangesetAttribution(
            changeset_id=changeset_id,
            kind=kind,
            published_by=username,
            batch_id=batch_id,
        )
        for changeset_id, kind, username, batch_id in rows
    }


async def dismiss_changeset(
    changeset_id: str,
    reason: DismissalReason,
    resolved_by_user_id: str | None = None,
) -> None:
    """This scrape will not go live — a reviewer said so, the run was cancelled, or it failed.

    The counterpart to publishing, and the other way a request leaves the review queue. Not a
    failure: a dismissed scrape keeps its evidence, it just never published.

    `reason` is required because the caller is the only thing that knows it. `status` and
    `resolved_by_user_id` can be read to guess, but both are mutable — so a guess made later
    could give a past event a meaning it never had.

    It lands in both `dismissed_reason` and the `dismiss_review` log: the column is state, which
    readers ask for; the log is the event, who dismissed it and when.

    Nothing to clean up on the way out: a scrape only *proposes* seats, and posts are created
    at publish. A dismissed changeset never minted one.

    The marking itself is `dismissals.mark_dismissed`, which is also where the check lives that
    this reason may leave this changeset's state — a run that produced no roster cannot be
    *rejected* by a person.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await dismissals_db.mark_dismissed(
            cur, [changeset_id], reason, resolved_by_user_id
        )
        await conn.commit()


class SupersededRoster(ValueError):
    """A newer roster for this jurisdiction is already live.

    An expected state, not a fault: two imports minutes apart leave two cards, and publishing
    the newer one makes the older one stale. Its own type so the API can say that rather than
    answering 500, but still a `ValueError` — every caller that already treated a refusal as one
    keeps working.
    """


async def _refuse_if_superseded(
    cur, changeset_id: str, jurisdiction_ocdid: str, last_seen_at
) -> None:
    """Refuse a roster older than one already published — a reviewer working an old card did not
    go and look at the source again."""
    await cur.execute(
        """
        SELECT changesets.id::text, changesets.updated_at
        FROM changesets
        WHERE changesets.jurisdiction_ocdid = %s
          AND changesets.published_at IS NOT NULL
          AND changesets.id::text <> %s
          AND changesets.updated_at > %s
        ORDER BY changesets.updated_at DESC
        LIMIT 1
        """,
        (jurisdiction_ocdid, changeset_id, last_seen_at),
    )
    newer = await cur.fetchone()
    if newer:
        raise SupersededRoster(
            f"Refusing to publish {changeset_id}: request {newer[0]} already published a "
            f"newer roster for {jurisdiction_ocdid} ({newer[1]} > {last_seen_at})."
        )


class UnpublishableChangeset(ValueError):
    """This changeset is not in a state that may publish.

    Its own type, like `SupersededRoster`: an expected refusal rather than a fault, so the API
    can say which it was.
    """


async def _refuse_if_not_publishable(cur, changeset_id: str) -> None:
    await cur.execute(
        """
        SELECT dismissed_at FROM changesets
        WHERE id::text = %s AND published_at IS NULL AND dismissed_at IS NOT NULL
        """,
        (changeset_id,),
    )
    row = await cur.fetchone()
    if row:
        raise UnpublishableChangeset(
            f"Refusing to publish {changeset_id}: dismissed_at={row[0]}."
        )


async def _record_publish(
    cur,
    changeset_id: str,
    jurisdiction_ocdid: str,
    resolved_by_user_id: str | None,
    changes: Change | None = None,
) -> None:
    # No `jurisdictions.scraped_at` stamp any more. It was written here on *every* publish
    # with no filter, so ten hand edits had dated a "scrape" for jurisdictions where nothing
    # was scraped — while `advances_last_seen`, computed a few lines up, was already asking
    # exactly that question for `memberships.last_seen_at`. Freshness derives now, from
    # published collection changesets: `LAST_COLLECTED_JOIN`.
    await cur.execute(
        """
        UPDATE changesets
           SET published_at = COALESCE(published_at, now()),
               -- A person stood behind this one. An auto-publish passes no user and leaves it
               -- NULL, which is the whole distinction the column exists to carry.
               verified_at = COALESCE(
                   verified_at, CASE WHEN %s::uuid IS NOT NULL THEN now() END
               ),
               -- Same chain as the dismissal: an auto-publish is the system publishing, not
               -- a publish with nobody behind it.
               resolved_by_user_id = COALESCE(%s, resolved_by_user_id, %s)
         WHERE id = %s
        """,
        (resolved_by_user_id, resolved_by_user_id, SYSTEM_USER_ID, changeset_id),
    )
    await record_change(
        cur,
        ActivityType.PUBLISH_REVIEW,
        resolved_by_user_id,
        jurisdiction_ocdid,
        changes=changes,
        changeset_id=changeset_id,
    )


async def _supersede_stale_cards(cur, changeset_id: str, jurisdiction_ocdid: str) -> None:
    """Same transaction, so a published roster and the cards it obsoletes cannot disagree."""
    last_seen_at = await get_updated_at(cur, changeset_id)
    stale = await dismissals_db.dismiss_superseded_by(
        cur, changeset_id, jurisdiction_ocdid, last_seen_at
    )
    if stale:
        logger.info(
            f"[{changeset_id}] Superseded {len(stale)} stale card(s) for "
            f"{jurisdiction_ocdid}: {stale}"
        )


async def _publish_review_edit(cur, changeset_id: str) -> None:
    """A review's edit goes live with its scrape, in the same transaction (9f)."""
    await cur.execute(
        f"""
        UPDATE changesets SET published_at = now()
         WHERE changesets.parent_changeset_id::text = %s AND {OPEN_REVIEW_EDIT}
        """,
        (changeset_id,),
    )


async def publish_changeset(
    changeset_id: str,
    jurisdiction_ocdid: str,
    resolved_by_user_id: str | None = None,
    changes: Change | None = None,
) -> int:
    """Make this changeset live, and rebuild the jurisdiction's roster from the facts.

    The changeset carries no roster of its own: its records are already stored, and publishing
    is what lets the fold see them. So a hand edit and a scrape publish the same way, and
    republishing is a no-op rather than a second write.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        last_seen_at = await get_updated_at(cur, changeset_id)
        await _refuse_if_superseded(cur, changeset_id, jurisdiction_ocdid, last_seen_at)
        await _refuse_if_not_publishable(cur, changeset_id)
        await _record_publish(
            cur, changeset_id, jurisdiction_ocdid, resolved_by_user_id, changes
        )
        await _publish_review_edit(cur, changeset_id)
        # After both publishes, so their facts are part of what this derives.
        written = await projection.rebuild_from_facts(cur, jurisdiction_ocdid, changeset_id)
        await _supersede_stale_cards(cur, changeset_id, jurisdiction_ocdid)
    return written
