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
from core.people_edits import with_asserted_values
from core.membership_proposal import ids_by_person_and_organization
from core.post_derivation import DerivedPost, MembershipBinding
from core.sinks.open_data_commit import ChangesetAttribution
from database import assertions, memberships, posts, source_records
from database.activity import record_change
from database.changeset_predicates import PUBLISHED
from database.changesets import get_updated_at
from database.database import get_pool
from database.people import PERSON_UPSERT, person_upsert_params
from database.users import SYSTEM_USER_ID
from schemas.activity import Change
from schemas.assertions import EntityType
from shared.utils.statuses import (
    COLLECTION_KINDS,
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


async def publish_attributions(changeset_ids: list[str]) -> dict[str, ChangesetAttribution]:
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
    """Put this roster's people in their posts, each in the organization its post derived.

    A membership is a binding: who holds a seat is only true once the scrape is accepted.
    """
    # Seats are created here, not at ingest: a scrape only proposes them, and publishing is what
    # accepts. `create_all` logs each mint against this changeset.
    post_ids = await posts.create_all(
        cur, jurisdiction_ocdid, derived, changeset_id
    )
    bindings: list[MembershipBinding] = []
    for post in derived:
        post_id = post_ids[(post.organization_id, post.role_id, post.division_ocdid)]
        for member in post.members:
            bindings.append(
                MembershipBinding(member=member, organization_id=post.organization_id, post_id=post_id)
            )
    if bindings:
        await memberships.close_moved_memberships(cur, bindings, last_seen_at)
        await memberships.upsert_open_memberships(cur, bindings, last_seen_at, advances_last_seen)
        membership_ids = ids_by_person_and_organization(
            await memberships.open_memberships(cur, [jurisdiction_ocdid])
        )
        await memberships.replace_membership_roles(cur, bindings, membership_ids)


def _people_by_organization(derived: list[DerivedPost]) -> dict[str, list[str]]:
    """Who this roster puts in each organization."""
    people: dict[str, list[str]] = {}
    for post in derived:
        for member in post.members:
            people.setdefault(post.organization_id, []).append(member.person_id)
    return people


async def _organizations_to_close_in(
    cur, changeset_id: str, people_here: dict[str, list[str]]
) -> list[str]:
    """The bodies `close_absent` runs in, one call each.

    The bodies it read a page for: one it never looked at keeps its people, and one whose
    extraction returned nobody closes nobody (`close_absent`'s own guard), because an empty result
    is a failed scrape more often than a dissolved body.

    A hand edit records evidence only for the people it adds, so a changeset with none falls back to
    the bodies its own roster puts people in. Leaving the last person out of a body therefore does
    not retire them: ending that membership is an explicit act now, not an omission.
    """
    read = await source_records.organizations_for_changeset(cur, changeset_id)
    return read or list(people_here)


async def _publish_people(
    cur,
    changeset_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str | None,
    changes: Change | None,
) -> int:
    """The part every publish shares: the guards, the people rows, and the publish record."""
    last_seen_at = await get_updated_at(cur, changeset_id)
    await _refuse_if_superseded(cur, changeset_id, jurisdiction_ocdid, last_seen_at)
    await _refuse_if_not_publishable(cur, changeset_id)

    incoming_ids = [str(person["id"]) for person in people]
    asserted = await assertions.asserted_values(cur, EntityType.PERSON, incoming_ids)
    rows = person_upsert_params(
        [with_asserted_values(person, asserted.get(str(person["id"]), {})) for person in people]
    )
    if rows:
        await cur.executemany(PERSON_UPSERT, rows)

    await _record_publish(cur, changeset_id, jurisdiction_ocdid, resolved_by_user_id, changes)
    return len(rows)


async def _close_claimed_and_supersede(cur, changeset_id: str, jurisdiction_ocdid: str) -> None:
    last_seen_at = await get_updated_at(cur, changeset_id)
    await memberships.close_claimed(cur, jurisdiction_ocdid, last_seen_at)
    await memberships.close_for_people_rejected_here(cur, jurisdiction_ocdid, last_seen_at)

    # Same transaction, so a published roster and the cards it obsoletes cannot disagree.
    stale = await dismissals_db.dismiss_superseded_by(
        cur, changeset_id, jurisdiction_ocdid, last_seen_at
    )
    if stale:
        logger.info(
            f"[{changeset_id}] Superseded {len(stale)} stale card(s) for "
            f"{jurisdiction_ocdid}: {stale}"
        )


async def publish_changeset(
    changeset_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str | None = None,
    derived: list[DerivedPost] | None = None,
    changes: Change | None = None,
) -> int:
    """A whole roster: every membership re-derived, and whoever the source stopped listing closed."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        written = await _publish_people(
            cur, changeset_id, jurisdiction_ocdid, people, resolved_by_user_id, changes
        )
        last_seen_at = await get_updated_at(cur, changeset_id)
        # `updated_at` orders superseding whatever the kind — a hand edit really is the newest
        # word. Whether it *dates a seat* is a different question, and only a source reading
        # answers it.
        read_from_a_source = await _collected_from_a_source(cur, changeset_id)
        if derived:
            await _bind_memberships(
                cur, changeset_id, jurisdiction_ocdid, derived, last_seen_at, read_from_a_source
            )

        # A person's claims first: publish applies what somebody said, then infers the rest from
        # what the source stopped listing.
        await _close_claimed_and_supersede(cur, changeset_id, jurisdiction_ocdid)
        people_here = _people_by_organization(derived or [])
        for organization_id in await _organizations_to_close_in(cur, changeset_id, people_here):
            await memberships.close_absent(
                cur, organization_id, people_here.get(organization_id, []), last_seen_at
            )
    return written


async def publish_hand_edit(
    changeset_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str,
    added: list[DerivedPost],
    removed_person_ids: list[str],
    changes: Change | None = None,
) -> int:
    """Only the people a hand edit touched: memberships for the ones it added, closed for the
    ones it removed.

    Nobody else's membership is re-derived or closed: `memberships.assign` already put people
    where a human said, and re-deriving from label text undid it.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        written = await _publish_people(
            cur, changeset_id, jurisdiction_ocdid, people, resolved_by_user_id, changes
        )
        last_seen_at = await get_updated_at(cur, changeset_id)
        if added:
            await _bind_memberships(
                cur, changeset_id, jurisdiction_ocdid, added, last_seen_at, advances_last_seen=False
            )
        await memberships.close_for_people(
            cur, jurisdiction_ocdid, removed_person_ids, last_seen_at
        )
        await _close_claimed_and_supersede(cur, changeset_id, jurisdiction_ocdid)
    return written
