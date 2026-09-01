"""The publish transaction: everything that becomes true when a scrape goes live.

One connection, one transaction. `people` and `jurisdictions.scraped_at` used to be written by
separate paths after the merge — `people` by reading the merged file back out of open-data
(`open_data_sync.sync_people`), `scraped_at` by a second call beside it. Publishing from the
database instead makes them one atomic fact, and removes the read-back that made GitHub the
authority for what is live.

This is the seam 2.5 extends: `posts` and `memberships` are derived at publish and belong in
*this* transaction, not a second publish path. Nothing here reads open-data.
"""

import logging

from core.post_derivation import DerivedPost
from core.people_edits import values_to_accept, with_stated_values
from database import assertions, memberships, organizations, posts
import database.requests as requests_db
from database.change_logs import record_dismissal
from database.database import get_pool
from database.people import PERSON_UPSERT, person_upsert_params
from database.pipeline_runs import get_sourced_at
from schemas.assertions import Assertion, AssertionKind, EntityType
from shared.utils.statuses import DismissalReason

logger = logging.getLogger(__name__)


async def record_open_data_url(request_id: str, url: str) -> None:
    """Where this request's data landed in open-data. Written after the commit, not with the
    publish, because the write is queued and retried — the publish is already a fact by then."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET open_data_url = %s WHERE id = %s", (url, request_id)
        )


async def dismiss_request(
    request_id: str,
    reason: DismissalReason,
    resolved_by_user_id: str | None = None,
) -> None:
    """This scrape will not go live — a reviewer said so, the run was cancelled, or it failed.

    The counterpart to publishing, and the other way a request leaves the review queue. Not a
    failure: a dismissed scrape keeps its evidence, it just never published.

    `reason` is required because the caller is the only thing that knows it. `status` and
    `resolved_by_user_id` can be read to guess, but both are mutable — so a guess made later
    could give a past event a meaning it never had.

    `resolved_by_user_id` is NULL when the machine gave up rather than a person deciding, and
    `COALESCE` means a later human resolution is never overwritten by a machine one.

    Nothing to clean up on the way out: a scrape only *proposes* seats, and posts are created
    at publish. A dismissed changeset never minted one.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE changesets
               SET dismissed_at = COALESCE(dismissed_at, now()),
                   resolved_by_user_id = COALESCE(%s, resolved_by_user_id)
             WHERE id = %s AND published_at IS NULL
            RETURNING jurisdiction_ocdid
            """,
            (resolved_by_user_id, request_id),
        )
        row = await cur.fetchone()
        # Only when the UPDATE matched: a request already published is left alone above, and
        # must not gain a dismissal in its history either.
        if row is not None:
            await record_dismissal(
                cur, request_id, row[0], resolved_by_user_id, reason
            )


class SupersededRoster(ValueError):
    """A newer roster for this jurisdiction is already live.

    An expected state, not a fault: two imports minutes apart leave two cards, and publishing
    the newer one makes the older one stale. Its own type so the API can say that rather than
    answering 500, but still a `ValueError` — every caller that already treated a refusal as one
    keeps working.
    """


async def _refuse_if_superseded(
    cur, request_id: str, jurisdiction_ocdid: str, last_seen_at
) -> None:
    """Refuse a roster older than one already published — a reviewer working an old card did not
    go and look at the source again."""
    await cur.execute(
        """
        SELECT r.id::text, r.sourced_at
        FROM changesets r
        WHERE r.jurisdiction_ocdid = %s
          AND r.published_at IS NOT NULL
          AND r.id::text <> %s
          AND r.sourced_at > %s
        ORDER BY r.sourced_at DESC
        LIMIT 1
        """,
        (jurisdiction_ocdid, request_id, last_seen_at),
    )
    newer = await cur.fetchone()
    if newer:
        raise SupersededRoster(
            f"Refusing to publish {request_id}: request {newer[0]} already published a "
            f"newer roster for {jurisdiction_ocdid} ({newer[1]} > {last_seen_at})."
        )


async def _record_publish(
    cur, request_id: str, jurisdiction_ocdid: str, resolved_by_user_id: str | None
) -> None:
    """Stamp the jurisdiction as scraped and the request as published.

    The FROM-join is a no-op when the request has no pipeline run, so `scraped_at` is never
    blanked; the COALESCE keeps the first publish's timestamp if one is replayed.
    """
    await cur.execute(
        """
        UPDATE jurisdictions j SET scraped_at = r.created_at
        FROM changesets r
        WHERE r.id = %s AND j.jurisdiction_ocdid = %s
        """,
        (request_id, jurisdiction_ocdid),
    )
    await cur.execute(
        """
        UPDATE changesets
           SET published_at = COALESCE(published_at, now()),
               resolved_by_user_id = COALESCE(%s, resolved_by_user_id)
         WHERE id = %s
        """,
        (resolved_by_user_id, request_id),
    )


async def _bind_memberships(
    cur,
    changeset_id: str,
    jurisdiction_ocdid: str,
    derived: list[DerivedPost],
    last_seen_at,
) -> None:
    """Put this roster's people in their posts.

    A membership is a binding: who holds a seat is only true once the scrape is accepted.
    Closing absentees is outside — it depends on the roster, not on `derived`.
    """
    organization_id = await organizations.find_or_create(cur, jurisdiction_ocdid)
    # Seats are created here, not at ingest: a scrape only proposes them, and publishing is what
    # accepts. `create_all` logs each mint against this changeset.
    post_ids = await posts.create_all(cur, jurisdiction_ocdid, derived, changeset_id)
    for post in derived:
        for member in post.members:
            await memberships.upsert(
                cur,
                member,
                post_ids[(post.role_id, post.division_ocdid)],
                organization_id,
                last_seen_at,
            )


async def _accept_published(cur, rows: list[dict], resolved_by_user_id: str | None) -> None:
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
    request_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str | None = None,
    derived: list[DerivedPost] | None = None,
) -> int:
    """Project one scrape's roster onto `people`, stamp it published, and bind the memberships.

    One transaction, so "published" and "what was published" cannot disagree; raises rather than
    swallowing. `last_seen_at` comes from the run, not from now — a scrape sat on for three
    weeks still read the source when it ran.

    Assertions apply here rather than at ingest, so the scrape stays what the source said.
    """
    incoming_ids = [str(person["id"]) for person in people]

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        last_seen_at = await get_sourced_at(cur, request_id)
        await _refuse_if_superseded(cur, request_id, jurisdiction_ocdid, last_seen_at)

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

        await _record_publish(cur, request_id, jurisdiction_ocdid, resolved_by_user_id)
        if derived:
            await _bind_memberships(
                cur, request_id, jurisdiction_ocdid, derived, last_seen_at
            )
        # Outside the guard: who is no longer on the roster is answered by the roster.
        await memberships.close_absent(
            cur, jurisdiction_ocdid, incoming_ids, last_seen_at
        )

        # Same transaction, so a published roster and the cards it obsoletes cannot disagree.
        stale = await requests_db.dismiss_superseded_by(
            cur, request_id, jurisdiction_ocdid, last_seen_at
        )
        if stale:
            logger.info(
                f"[{request_id}] Superseded {len(stale)} stale card(s) for "
                f"{jurisdiction_ocdid}: {stale}"
            )

    return len(rows)
