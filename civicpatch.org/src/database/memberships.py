"""Database queries for `memberships` — a person holding a post over time.

Three cases, and they are the whole model:

  found on the same post       advance `last_seen_at`
  found on a different post    close the old membership, open a new one
  not found at all             close it

Closing rather than moving is what preserves history: a person who moves from Ward 3 to
Mayor leaves a closed Ward 3 membership with its own window, which is what the roster
timeline reads. One *open* membership per person per body; closed ones pile up freely.

`closed_at` is ours and `end_date` is the source's — a sitting member has a future
`end_date` and no `closed_at`; someone who quietly vanished has a `closed_at` and no
`end_date`, because disappearing from a page says they are gone, not when they went.
"""


async def record(
    cur,
    person_id: str,
    post_id: str,
    organization_id: str,
    observed_at,
    label: str | None = None,
    start_date=None,
    end_date=None,
) -> str:
    """Open this person's membership of this post, or advance it. Returns its id.

    Any open membership they hold on a *different* post in the same body is closed first, so
    the insert below can only ever collide with the same-post case. That ordering is what
    makes "one open per body" hold without the insert needing to know which case it is in.

    `label`, `start_date` and `end_date` come from the scrape and are overwritten on every
    pass. That is the surface `field_locks` will guard; until it exists, a manual correction
    to any of the three is lost on the next publish.
    """
    await cur.execute(
        """
        UPDATE memberships SET closed_at = %s
        WHERE person_id = %s AND organization_id = %s
          AND closed_at IS NULL AND post_id <> %s
        """,
        (observed_at, person_id, organization_id, post_id),
    )

    await cur.execute(
        """
        INSERT INTO memberships
            (post_id, organization_id, person_id, label, start_date, end_date,
             first_seen_at, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (person_id, organization_id) WHERE closed_at IS NULL
        DO UPDATE SET
            last_seen_at = GREATEST(memberships.last_seen_at, EXCLUDED.last_seen_at),
            label = EXCLUDED.label,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date
        RETURNING id::text
        """,
        (
            post_id,
            organization_id,
            person_id,
            label,
            start_date,
            end_date,
            observed_at,
            observed_at,
        ),
    )
    return (await cur.fetchone())[0]


async def close_absent(
    cur, jurisdiction_ocdid: str, present_person_ids: list[str], closed_at
) -> int:
    """Close open memberships in this jurisdiction for anyone the scrape did not name.

    An empty roster closes nobody: that is a failed scrape, not a dissolved council. Same
    guard `publish_request` already applies before retiring people.
    """
    if not present_person_ids:
        return 0

    await cur.execute(
        """
        UPDATE memberships m SET closed_at = %s
        FROM posts p
        WHERE m.post_id = p.id
          AND p.jurisdiction_ocdid = %s
          AND m.closed_at IS NULL
          AND m.person_id <> ALL(%s)
        """,
        (closed_at, jurisdiction_ocdid, present_person_ids),
    )
    return cur.rowcount


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    """Open memberships with the post they sit on — the person-axis read."""
    await cur.execute(
        """
        SELECT m.id::text, m.person_id::text, m.post_id::text, m.label,
               m.start_date, m.end_date, m.first_seen_at, m.last_seen_at,
               p.role_id, p.division_ocdid
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        WHERE p.jurisdiction_ocdid = %s AND m.closed_at IS NULL
        ORDER BY p.role_id, p.division_ocdid
        """,
        (jurisdiction_ocdid,),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]
