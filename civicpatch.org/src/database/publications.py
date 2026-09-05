"""The publish transaction: everything that becomes true when a scrape goes live.

One connection, one transaction. `people` used to be written by a separate path after the
merge, by reading the merged file back out of open-data (`open_data_sync.sync_people`).
Publishing from the
database instead makes them one atomic fact, and removes the read-back that made GitHub the
authority for what is live.

This is the seam 2.5 extends: `posts` and `memberships` are derived at publish and belong in
*this* transaction, not a second publish path. Nothing here reads open-data.
"""

import logging

import database.changesets as changesets_db
import database.dismissals as dismissals_db
from core.people_edits import values_to_accept, with_stated_values
from core.post_derivation import DerivedPost
from database import assertions, memberships, organizations, posts
from database.change_logs import record_change
from database.changesets import get_updated_at
from database.database import get_pool
from database.people import PERSON_UPSERT, person_upsert_params
from database.users import SYSTEM_USER_ID
from schemas.assertions import Assertion, AssertionKind, EntityType
from shared.utils.statuses import (
    COLLECTION_KINDS,
    ChangeLogType,
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


async def dismiss_request(
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
    cur, changeset_id: str, jurisdiction_ocdid: str, resolved_by_user_id: str | None
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
               -- Same chain as the dismissal: an auto-publish is the system publishing, not
               -- a publish with nobody behind it.
               resolved_by_user_id = COALESCE(%s, resolved_by_user_id, %s)
         WHERE id = %s
        """,
        (resolved_by_user_id, SYSTEM_USER_ID, changeset_id),
    )
    await record_change(
        cur,
        ChangeLogType.PUBLISH_REVIEW,
        resolved_by_user_id,
        jurisdiction_ocdid,
        changeset_id=changeset_id,
    )


async def _collected_from_a_source(cur, changeset_id: str) -> bool:
    await cur.execute(
        "SELECT kind FROM changesets WHERE id::text = %s", (changeset_id,)
    )
    row = await cur.fetchone()
    return bool(row) and row[0] in COLLECTION_KINDS


async def _bind_memberships(
    cur,
    changeset_id: str,
    jurisdiction_ocdid: str,
    derived: list[DerivedPost],
    last_seen_at,
    advances_last_seen: bool,
) -> None:
    """Put this roster's people in their posts.

    A membership is a binding: who holds a seat is only true once the scrape is accepted.
    Closing absentees is outside — it depends on the roster, not on `derived`.
    """
    # The changeset's own organization, not "the jurisdiction's one" — a review is about one
    # body, and `posts_identity_uq` scopes a post's identity to it.
    organization_id = await organizations.find_or_create_for_changeset(
        cur, changeset_id, jurisdiction_ocdid
    )
    # Seats are created here, not at ingest: a scrape only proposes them, and publishing is what
    # accepts. `create_all` logs each mint against this changeset.
    post_ids = await posts.create_all(
        cur, jurisdiction_ocdid, organization_id, derived, changeset_id
    )
    for post in derived:
        for member in post.members:
            await memberships.upsert(
                cur,
                member,
                post_ids[(post.role_id, post.division_ocdid)],
                organization_id,
                last_seen_at,
                advances_last_seen=advances_last_seen,
            )


async def _accept_published(
    cur, rows: list[dict], resolved_by_user_id: str | None
) -> None:
    """Accept every value in the roster on the publisher's behalf.

    Nothing without a user: an unattended publish read nothing and judged nothing.
    """
    if not resolved_by_user_id:
        return
    for row in rows:
        for field, value in values_to_accept(row):
            await assertions.upsert(
                cur,
                Assertion(
                    entity_type=EntityType.PERSON,
                    entity_id=row["id"],
                    field_path=field,
                    kind=AssertionKind.ACCEPT,
                    value=value,
                ),
                resolved_by_user_id,
            )


async def publish_request(
    changeset_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str | None = None,
    derived: list[DerivedPost] | None = None,
) -> int:
    incoming_ids = [str(person["id"]) for person in people]

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        last_seen_at = await get_updated_at(cur, changeset_id)
        # `updated_at` orders superseding whatever the kind — a hand edit really is the newest
        # word. Whether it *dates a seat* is a different question, and only a source reading
        # answers it.
        advances_last_seen = await _collected_from_a_source(cur, changeset_id)
        await _refuse_if_superseded(cur, changeset_id, jurisdiction_ocdid, last_seen_at)
        await _refuse_if_not_publishable(cur, changeset_id)

        stated = await assertions.stated_values(cur, EntityType.PERSON, incoming_ids)
        rows = person_upsert_params(
            [
                with_stated_values(person, stated.get(str(person["id"]), {}))
                for person in people
            ]
        )
        if rows:
            await cur.executemany(PERSON_UPSERT, rows)

        await _accept_published(cur, rows, resolved_by_user_id)

        await _record_publish(
            cur, changeset_id, jurisdiction_ocdid, resolved_by_user_id
        )
        if derived:
            await _bind_memberships(
                cur,
                changeset_id,
                jurisdiction_ocdid,
                derived,
                last_seen_at,
                advances_last_seen,
            )
        # Outside the guard: who is no longer on the roster is answered by the roster.
        await memberships.close_absent(
            cur, jurisdiction_ocdid, incoming_ids, last_seen_at
        )

        # Same transaction, so a published roster and the cards it obsoletes cannot disagree.
        stale = await dismissals_db.dismiss_superseded_by(
            cur, changeset_id, jurisdiction_ocdid, last_seen_at
        )
        if stale:
            logger.info(
                f"[{changeset_id}] Superseded {len(stale)} stale card(s) for "
                f"{jurisdiction_ocdid}: {stale}"
            )

    return len(rows)
