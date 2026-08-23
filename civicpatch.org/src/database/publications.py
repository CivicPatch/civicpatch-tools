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
from database import divisions, memberships, organizations, posts
from database.database import get_pool
from database.people import people_rows
from database.pipeline_runs import run_updated_at


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
    failure: a dismissed scrape keeps its evidence and its data_json, it just never published.

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


async def publish_request(
    request_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str | None = None,
    derived: list[DerivedPost] | None = None,
) -> int:
    """Project one scrape's roster onto `people`, stamp the jurisdiction as scraped, and mark
    the request published.

    Returns the number of people written. Raises rather than swallowing: a publish that cannot
    record what it published must fail loudly, unlike the submit-time evidence write, where
    losing evidence is better than losing the submit.

    `derived` carries the posts this roster implies. Memberships are written here rather than
    at ingest because a membership is a binding: a post can be proposed for review, but who
    holds it is only true once the scrape is accepted. Posts are re-ensured on the way through
    because ingest is never fatal, so they may be missing.
    """
    rows = people_rows(people)
    incoming_ids = [row[0] for row in rows]

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # `pipeline_runs.updated_at`, not publish time: a scrape sat on for three weeks still
        # read the source when it ran. Same value orders the guard below and stamps memberships.
        last_seen_at = await run_updated_at(cur, request_id)

        # Which scrape read the source more recently — a reviewer editing an old roster did
        # not go and look again.
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

        if rows:
            await cur.executemany(
                """
                INSERT INTO people (id, jurisdiction_ocdid, data, updated_at, status)
                VALUES (%s, %s, %s, %s, 'active')
                ON CONFLICT (id) DO UPDATE
                   SET data = EXCLUDED.data,
                       updated_at = EXCLUDED.updated_at,
                       status = 'active'
                """,
                rows,
            )

        # Anyone the roster no longer names has left office. `inactive` rather than deleted,
        # so membership history survives. An empty roster is not treated as "retire everyone" — that is
        # a failed scrape, not a dissolved council.
        if incoming_ids:
            await cur.execute(
                """
                UPDATE people SET status = 'inactive'
                WHERE jurisdiction_ocdid = %s AND id != ALL(%s)
                """,
                (jurisdiction_ocdid, incoming_ids),
            )

        # Moved verbatim from publish_side_effects. The FROM-join makes it a no-op when the
        # request has no pipeline run, so scraped_at is never blanked.
        await cur.execute(
            """
            UPDATE jurisdictions j SET scraped_at = pr.created_at
            FROM pipeline_runs pr
            WHERE pr.request_id = %s AND j.jurisdiction_ocdid = %s
            """,
            (request_id, jurisdiction_ocdid),
        )

        # In the same transaction as the roster: "published" and "what was published" must
        # never disagree. COALESCE keeps the first publish's timestamp if one is replayed.
        await cur.execute(
            """
            UPDATE requests
               SET published_at = COALESCE(published_at, now()),
                   resolved_by_user_id = COALESCE(%s, resolved_by_user_id)
             WHERE id = %s
            """,
            (resolved_by_user_id, request_id),
        )

        if derived:
            organization_id = await organizations.find_or_create(
                cur, jurisdiction_ocdid
            )
            for post in derived:
                await divisions.find_or_create(
                    cur, post.division_ocdid, jurisdiction_ocdid
                )
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
            await memberships.close_absent(
                cur, jurisdiction_ocdid, incoming_ids, last_seen_at
            )

    return len(rows)
