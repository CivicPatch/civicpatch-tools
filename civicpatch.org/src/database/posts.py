"""Database queries for `posts` — a seat-type within a body.

Identity is the parsed triple `(organization_id, role_id, division_ocdid)` and nothing else.
No free text is in the key, so nothing a human types can fork a post: renaming one cannot
make the next scrape miss it.

MINT-ONLY WRITES, absolutely. `record` sets a post's columns when it creates one and writes
nothing at all when it matches one — a match is a pure lookup. That is what keeps `label` and
`headcount` human-owned with no lock table: there is no update path to lose them through.

Whether a human vouched for a post is not stored either — 121 dropped `status` for it.
Memberships are written only at publish, and publishing is a named human act, so a post with
any member was endorsed by a person and one without was only ever proposed by a scrape.

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

    A minted post is unvouched-for, and nothing records that — it follows from having no
    members, since memberships are written only at publish. 121 dropped the `status` column
    that used to say it, along with the promotion path that never existed to change it.

    `headcount` applies only on mint. A later scrape finding a different number of people must
    not overwrite a figure somebody typed — which is why the count cannot simply be recomputed
    on every pass.

    `DO NOTHING` means a match writes nothing, so the SELECT below is not a fallback for a
    rare case: it is the normal path every time a post already exists.
    """
    await cur.execute(
        """
        INSERT INTO posts
            (jurisdiction_ocdid, organization_id, role_id, division_ocdid, headcount)
        VALUES (%s, %s, %s, %s, %s)
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


async def create_if_absent(
    cur,
    jurisdiction_ocdid: str,
    organization_id: str,
    role_id: str,
    division_ocdid: str,
    label: str | None = None,
    headcount: int = 1,
) -> str | None:
    """Insert a post, or return None if the identity triple is already taken.

    A person asserting a seat exists, where `find_or_create` is a scrape proposing one — same
    row, and the only mechanical difference is the return: this caller has to tell "created"
    from "already there" apart to answer 409.
    """
    await cur.execute(
        """
        INSERT INTO posts
            (jurisdiction_ocdid, organization_id, role_id, division_ocdid, label, headcount)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (organization_id, role_id, division_ocdid) DO NOTHING
        RETURNING id::text
        """,
        (
            jurisdiction_ocdid,
            organization_id,
            role_id,
            division_ocdid,
            label,
            headcount,
        ),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def update_human_fields(
    cur, post_id: str, label: str | None, headcount: int
) -> bool:
    """Set the two columns a person owns. Returns whether the post existed.

    The only update path that touches a post. Derivation is mint-only precisely so this is the
    only thing that can reach `label` and `headcount`.
    """
    await cur.execute(
        "UPDATE posts SET label = %s, headcount = %s WHERE id::text = %s",
        (label, headcount, post_id),
    )
    return cur.rowcount > 0


async def delete_if_unheld(cur, post_id: str) -> bool:
    """Remove a post nobody has ever held. Returns whether it went.

    A post with no memberships was proposed by a scrape and endorsed by no one — the same
    condition that reads as unverified. Deleting it is what "a person clears them" meant in the
    no-auto-delete decision.

    A post *with* memberships is history, including closed ones, and refusing here is what
    keeps the roster timeline answerable. The FK would refuse anyway; this makes it a 409
    rather than a 500.
    """
    await cur.execute(
        """
        DELETE FROM posts
        WHERE id::text = %s
          AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.post_id = posts.id)
        """,
        (post_id,),
    )
    return cur.rowcount > 0


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    """Every post in a jurisdiction with its current holder count — the roster read."""
    await cur.execute(
        """
        SELECT p.id::text, p.organization_id::text, p.role_id, p.division_ocdid,
               p.label, p.headcount,
               -- Endorsed by a person, not merely proposed by a scrape: memberships are
               -- written only at publish, and publishing is a named human act.
               count(m.id) > 0 AS verified,
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
    """Posts a person once endorsed that no scrape has produced since `cutoff`.

    Previously filtered `status = 'active'`, which no post ever held — `find_or_create` minted
    `candidate` and nothing promoted it, so this could never return a row. 121 dropped the
    column; the HAVING now carries the whole condition.

    A post with no memberships is excluded by that HAVING, which is the same test as "was it
    ever endorsed": nothing has been seen in it, so it cannot have stopped being seen. That
    also excludes every post in a jurisdiction awaiting its first publish — correctly, since
    a seat nobody has confirmed is not absent, only unconfirmed.
    """
    await cur.execute(
        """
        SELECT p.id::text, p.role_id, p.division_ocdid, p.label,
               max(m.last_seen_at) AS last_seen_at
        FROM posts p
        LEFT JOIN memberships m ON m.post_id = p.id
        WHERE p.jurisdiction_ocdid = %s
        GROUP BY p.id
        HAVING max(m.last_seen_at) < %s
        ORDER BY max(m.last_seen_at)
        """,
        (jurisdiction_ocdid, cutoff),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]
