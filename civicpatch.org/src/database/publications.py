"""The publish transaction: everything that becomes true when a scrape goes live.

One connection, one transaction. `people` and `jurisdictions.scraped_at` used to be written by
separate paths after the merge — `people` by reading the merged file back out of open-data
(`open_data_sync.sync_people`), `scraped_at` by a second call beside it. Publishing from the
database instead makes them one atomic fact, and removes the read-back that made GitHub the
authority for what is live.

This is the seam 2.5 extends: `posts` and `memberships` are derived at publish and belong in
*this* transaction, not a second publish path. Nothing here reads open-data.
"""

from core.post_derivation import DerivedPost
from core.people_edits import values_to_accept, with_stated_values
from database import assertions, divisions, memberships, organizations, posts
from database.database import get_pool
from database.people import PERSON_UPSERT, person_upsert_params
from database.pipeline_runs import run_updated_at
from schemas.assertions import Assertion, AssertionKind, EntityType


async def record_open_data_url(request_id: str, url: str) -> None:
    """Where this request's data landed in open-data. Written after the commit, not with the
    publish, because the write is queued and retried — the publish is already a fact by then."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE requests SET open_data_url = %s WHERE id = %s", (url, request_id)
        )


async def dismiss_request(
    request_id: str, resolved_by_user_id: str | None = None
) -> None:
    """This scrape will not go live — a reviewer said so, or the run was cancelled.

    The counterpart to publishing, and the other way a request leaves the review queue. Not a
    failure: a dismissed scrape keeps its evidence, it just never published.

    `resolved_by_user_id` is NULL when the machine gave up rather than a person deciding, and
    `COALESCE` means a later human resolution is never overwritten by a machine one.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE requests
               SET dismissed_at = COALESCE(dismissed_at, now()),
                   resolved_by_user_id = COALESCE(%s, resolved_by_user_id)
             WHERE id = %s AND published_at IS NULL
            """,
            (resolved_by_user_id, request_id),
        )


async def _refuse_if_superseded(
    cur, request_id: str, jurisdiction_ocdid: str, last_seen_at
) -> None:
    """Refuse a roster older than one already published — a reviewer working an old card did not
    go and look at the source again."""
    await cur.execute(
        """
        SELECT r.id::text, run.updated_at
        FROM requests r
        JOIN pipeline_runs run ON run.request_id = r.id
        WHERE r.jurisdiction_ocdid = %s
          AND r.published_at IS NOT NULL
          AND r.id::text <> %s
          AND run.updated_at > %s
        ORDER BY run.updated_at DESC
        LIMIT 1
        """,
        (jurisdiction_ocdid, request_id, last_seen_at),
    )
    newer = await cur.fetchone()
    if newer:
        raise ValueError(
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
        UPDATE jurisdictions j SET scraped_at = pr.created_at
        FROM pipeline_runs pr
        WHERE pr.request_id = %s AND j.jurisdiction_ocdid = %s
        """,
        (request_id, jurisdiction_ocdid),
    )
    await cur.execute(
        """
        UPDATE requests
           SET published_at = COALESCE(published_at, now()),
               resolved_by_user_id = COALESCE(%s, resolved_by_user_id)
         WHERE id = %s
        """,
        (resolved_by_user_id, request_id),
    )


async def _bind_memberships(
    cur,
    jurisdiction_ocdid: str,
    derived: list[DerivedPost],
    last_seen_at,
) -> None:
    """Put this roster's people in their posts.

    Here rather than at ingest because a membership is a binding: a post can be proposed, but
    who holds it is only true once the scrape is accepted.

    Closing absentees is *not* here, though it used to be. It depends on the roster, not on the
    derivation, and this runs only `if derived` — so a publish whose post derivation failed
    (`_get_derived_posts` swallows and returns `[]`) would have retired nobody.
    """
    organization_id = await organizations.find_or_create(cur, jurisdiction_ocdid)
    for post in derived:
        await divisions.find_or_create(cur, post.division_ocdid, jurisdiction_ocdid)
        post_id = await posts.find_or_create(
            cur,
            jurisdiction_ocdid,
            organization_id,
            post.role_id,
            post.division_ocdid,
            headcount=post.headcount,
        )
        for member in post.members:
            await memberships.upsert(
                cur,
                member.person_id,
                post_id,
                organization_id,
                last_seen_at,
                designations=member.designations,
                unmatched_text=member.unmatched_text,
                source_labels=member.source_labels,
                role_ids=member.role_ids,
                label=member.label,
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
        last_seen_at = await run_updated_at(cur, request_id)
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
            await _bind_memberships(cur, jurisdiction_ocdid, derived, last_seen_at)
        # Outside the guard: who is no longer on the roster is answered by the roster.
        await memberships.close_absent(
            cur, jurisdiction_ocdid, incoming_ids, last_seen_at
        )

    return len(rows)
