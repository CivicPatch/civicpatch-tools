"""Database queries for `posts` — a seat-type within a body.

Identity is the parsed triple `(organization_id, role_id, division_ocdid)` and nothing else.
No free text is in the key, so nothing a human types can fork a post: renaming one cannot
make the next scrape miss it.

MINT-ONLY WRITES, absolutely. `record` sets a post's columns when it creates one and writes
nothing at all when it matches one — a match is a pure lookup. That is what keeps `label`,
`headcount` and `status` human-owned with no lock table: there is no update path to lose them
through.

"When did a scrape last produce this post" is not stored, because it is
`MAX(memberships.last_seen_at)` — a post is produced exactly when somebody parses into it,
and that same pass stamps their membership.
"""


async def find_or_create(
    cur,
    jurisdiction_ocdid: str,
    organization_id: str,
    role_id: str,
    division_ocdid: str,
    headcount: int = 1,
) -> str:
    """Make sure this post exists. Returns its id, minted or matched.

    A minted post is `candidate`: a scrape proposing a seat is not the same as somebody
    asserting one exists, and a reviewer promotes it via NEW_POST. Written out rather than
    left to the column default so this module states its own behaviour — and so the human
    "declare a post" path, which must mint `active`, cannot inherit this one by accident.

    `headcount` applies only on mint. A later scrape finding a different number of people must
    not overwrite a figure somebody typed — which is why the count cannot simply be recomputed
    on every pass.

    `DO NOTHING` means a match writes nothing, so the SELECT below is not a fallback for a
    rare case: it is the normal path every time a post already exists.
    """
    await cur.execute(
        """
        INSERT INTO posts
            (jurisdiction_ocdid, organization_id, role_id, division_ocdid, headcount, status)
        VALUES (%s, %s, %s, %s, %s, 'candidate')
        ON CONFLICT (organization_id, role_id, division_ocdid) DO NOTHING
        RETURNING id::text
        """,
        (jurisdiction_ocdid, organization_id, role_id, division_ocdid, headcount),
    )
    minted = await cur.fetchone()
    if minted:
        return minted[0]

    await cur.execute(
        """
        SELECT id::text FROM posts
        WHERE organization_id = %s AND role_id = %s AND division_ocdid = %s
        """,
        (organization_id, role_id, division_ocdid),
    )
    return (await cur.fetchone())[0]


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    """Every post in a jurisdiction with its current holder count — the roster read."""
    await cur.execute(
        """
        SELECT p.id::text, p.organization_id::text, p.role_id, p.division_ocdid,
               p.label, p.headcount, p.status,
               count(m.id) FILTER (WHERE m.closed_at IS NULL) AS holders,
               max(m.last_seen_at) AS last_seen_at
        FROM posts p
        LEFT JOIN memberships m ON m.post_id = p.id
        WHERE p.jurisdiction_ocdid = %s
        GROUP BY p.id
        ORDER BY p.role_id, p.division_ocdid
        """,
        (jurisdiction_ocdid,),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def unseen_since(cur, jurisdiction_ocdid: str, cutoff) -> list[dict]:
    """Active posts no scrape has produced since `cutoff` — what raises ABSENT_POST.

    A post with no memberships at all is excluded by the HAVING: nothing has ever been seen
    in it, which is how a seat somebody declared reads, and that is not absent just because
    the source never mentioned it.
    """
    await cur.execute(
        """
        SELECT p.id::text, p.role_id, p.division_ocdid, p.label,
               max(m.last_seen_at) AS last_seen_at
        FROM posts p
        LEFT JOIN memberships m ON m.post_id = p.id
        WHERE p.jurisdiction_ocdid = %s AND p.status = 'active'
        GROUP BY p.id
        HAVING max(m.last_seen_at) < %s
        ORDER BY max(m.last_seen_at)
        """,
        (jurisdiction_ocdid, cutoff),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]
