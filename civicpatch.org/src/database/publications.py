"""The publish transaction: everything that becomes true when a scrape goes live.

One connection, one transaction. `people` and `jurisdictions.scraped_at` used to be written by
separate paths after the merge — `people` by reading the merged file back out of open-data
(`open_data_sync.sync_people`), `scraped_at` by a second call beside it. Publishing from the
database instead makes them one atomic fact, and removes the read-back that made GitHub the
authority for what is live.

This is the seam 2.5 extends: `posts` and `memberships` are derived at publish and belong in
*this* transaction, not a second publish path. Nothing here reads open-data.
"""

from database.database import get_pool
from database.people import people_rows


async def publish_request(
    request_id: str, jurisdiction_ocdid: str, people: list[dict]
) -> int:
    """Project one scrape's roster onto `people` and stamp the jurisdiction as scraped.

    Returns the number of people written. Raises rather than swallowing: a publish that cannot
    record what it published must fail loudly, unlike the submit-time evidence write, where
    losing evidence is better than losing the submit.
    """
    rows = people_rows(people)
    incoming_ids = [row[0] for row in rows]

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
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
        # so seat history survives. An empty roster is not treated as "retire everyone" — that is
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

    return len(rows)
