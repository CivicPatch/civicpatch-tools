"""Reading posts: one, many, a jurisdiction's, a state's, and who held each."""

from shared.schemas import Post
from core.post_grouping import group_by_organization
from database import claims, organizations
from database.database import get_pool
from database.post_claims import with_claims
from schemas.claims import EntityType

async def get_holder_names(post_ids: list[str]) -> dict[str, list[str]]:
    """Everyone who holds or held each post, by post id. A post nobody held is absent."""
    if not post_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT memberships.post_id::text,
                   array_agg(DISTINCT coalesce(people.name, 'someone unnamed'))
            FROM memberships JOIN people ON people.id = memberships.person_id
            WHERE memberships.post_id = ANY(%s::uuid[])
            GROUP BY memberships.post_id
            """,
            (post_ids,),
        )
        return {post_id: names for post_id, names in await cur.fetchall()}


async def get_many(cur, post_ids: list[str]) -> dict[str, Post]:
    """Posts by id. An id with no post is absent rather than None."""
    if not post_ids:
        return {}
    await cur.execute(
        """
        SELECT posts.id::text, posts.jurisdiction_ocdid, posts.organization_id::text,
               posts.role_id, posts.division_ocdid,
               post_role_label(posts.organization_id, posts.role_id) AS role_label
        FROM posts
        WHERE posts.id::text = ANY(%s)
        """,
        (post_ids,),
    )
    columns = [column.name for column in cur.description or []]
    rows = [dict(zip(columns, row)) for row in await cur.fetchall()]
    claimed = await claims.claimed_values(cur, EntityType.POST, [row["id"] for row in rows])
    found = [Post(**with_claims(row, claimed.get(row["id"], {}))) for row in rows]
    return {post.id: post for post in found}


async def get(cur, post_id: str) -> Post | None:
    """One post by id, or None. `assign` takes the organization from here, never from the
    caller, so a request cannot name a mismatched pair."""
    return (await get_many(cur, [post_id])).get(post_id)


async def identities_by_id(cur, post_ids: list[str]) -> dict[str, dict]:
    """The `(organization_id, role_id, division_ocdid)` of each named post — its identity, and
    all the derivation needs from a post a human picked.

    Batched: a roster is read at once, and one query per picked person would put the number of
    round trips in the reviewer's hands.
    """
    if not post_ids:
        return {}
    await cur.execute(
        """
        SELECT id::text, organization_id::text, role_id, division_ocdid
        FROM posts WHERE id::text = ANY(%s)
        """,
        (post_ids,),
    )
    columns = [column.name for column in cur.description or []]
    return {row[0]: dict(zip(columns, row)) for row in await cur.fetchall()}


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    by_jurisdiction = await list_for_jurisdictions(cur, [jurisdiction_ocdid])
    return by_jurisdiction.get(jurisdiction_ocdid, [])


async def list_for_jurisdictions(cur, jurisdiction_ocdids: list[str]) -> dict[str, list[dict]]:
    """Every post in each jurisdiction.

    Undated on purpose. A post is not a temporal fact — one minted last week still belongs in
    a June answer — and who holds it at a given moment is the memberships read, which windows
    on `opened_at` and `closed_at`. Vouching is not dated either: winding the clock back
    does not un-vouch a post.
    """
    await cur.execute(
        f"""
        SELECT posts.id::text, posts.jurisdiction_ocdid, posts.organization_id::text,
               posts.role_id, posts.division_ocdid,
               post_role_label(posts.organization_id, posts.role_id) AS role_label
        FROM posts
        WHERE posts.jurisdiction_ocdid = ANY(%(jurisdiction_ocdids)s)
        ORDER BY posts.role_id, posts.division_ocdid
        """,
        {"jurisdiction_ocdids": jurisdiction_ocdids},
    )
    columns = [column.name for column in cur.description or []]
    rows = [dict(zip(columns, row)) for row in await cur.fetchall()]
    claimed = await claims.claimed_values(cur, EntityType.POST, [row["id"] for row in rows])
    by_jurisdiction: dict[str, list[dict]] = {}
    for row in rows:
        by_jurisdiction.setdefault(row["jurisdiction_ocdid"], []).append(
            with_claims(row, claimed.get(row["id"], {}))
        )
    return by_jurisdiction


async def list_page_for_state(
    state: str, limit: int, offset: int
) -> tuple[int, list[dict]]:
    """One page of every post in a state, and the total behind it.

    Same projection as `list_for_jurisdiction`, plus the jurisdiction each belongs to — a
    state-wide read has to say which town a seat is in.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT COUNT(*) OVER() AS total,
                   posts.jurisdiction_ocdid,
                   posts.id::text, posts.organization_id::text, posts.role_id,
                   posts.division_ocdid,
                   post_role_label(posts.organization_id, posts.role_id) AS role_label
            FROM posts
            WHERE posts.jurisdiction_ocdid LIKE %(prefix)s
            ORDER BY posts.jurisdiction_ocdid, posts.role_id, posts.division_ocdid
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {
                "prefix": f"ocd-jurisdiction/country:us/state:{state.lower()}%",
                "limit": limit,
                "offset": offset,
            },
        )
        rows = await cur.fetchall()
        columns = [column.name for column in cur.description or []]
        if not rows:
            return 0, []
        dict_rows = [{k: v for k, v in zip(columns, row) if k != "total"} for row in rows]
        claimed = await claims.claimed_values(
            cur, EntityType.POST, [row["id"] for row in dict_rows]
        )
    total = rows[0][0]
    return total, [with_claims(row, claimed.get(row["id"], {})) for row in dict_rows]


async def ids_by_identity(
    cur, organization_ids: list[str]
) -> dict[tuple[str, str, str], str]:
    """`(organization, role_id, division_ocdid) -> post id`. Reverse of `identities_by_id`, so
    `propose` can stay pure and unaware of ids.

    Keyed on the organization because that is what `posts_identity_uq` is keyed on. Keyed on the
    jurisdiction it was unambiguous only while a jurisdiction had one body: two bodies with the
    same role and division would collapse onto one key and the dict would keep whichever came
    last.
    """
    if not organization_ids:
        return {}
    await cur.execute(
        """
        SELECT organization_id::text, role_id, division_ocdid, id::text
        FROM posts WHERE organization_id::text = ANY(%s)
        """,
        (organization_ids,),
    )
    return {(row[0], row[1], row[2]): row[3] for row in await cur.fetchall()}


async def list_by_organization(jurisdiction_ocdid: str) -> list[dict]:
    """Every body in a jurisdiction with its posts."""
    by_jurisdiction = await list_by_organization_for_jurisdictions([jurisdiction_ocdid])
    return by_jurisdiction[jurisdiction_ocdid]


async def list_by_organization_for_jurisdictions(
    jurisdiction_ocdids: list[str],
) -> dict[str, list[dict]]:
    """`list_by_organization` for many jurisdictions: two queries, whatever the count."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_rows = await organizations.list_for_jurisdictions(cur, jurisdiction_ocdids)
        post_rows = await list_for_jurisdictions(cur, jurisdiction_ocdids)
    return {
        jurisdiction_ocdid: group_by_organization(
            organization_rows.get(jurisdiction_ocdid, []),
            post_rows.get(jurisdiction_ocdid, []),
        )
        for jurisdiction_ocdid in jurisdiction_ocdids
    }


async def ids_in_organizations(
    cur, post_ids: list[str], organization_ids: list[str]
) -> set[str]:
    """Which of these posts belong to those bodies.

    A person can hold one post per organization, so a reviewer's accepted posts may span several:
    this is what picks out the ones the review in front of them is about.
    """
    if not post_ids or not organization_ids:
        return set()
    await cur.execute(
        "SELECT id::text FROM posts WHERE organization_id::text = ANY(%s) AND id::text = ANY(%s)",
        (organization_ids, post_ids),
    )
    return {row[0] for row in await cur.fetchall()}
