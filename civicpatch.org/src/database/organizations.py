"""Database queries for `organizations` — the body a post belongs to.

Populated lazily: a row is minted the first time a post needs one, never synced ahead from
`jurisdictions`. There is no 7,104-row sync path to keep correct, and the table then holds
exactly the bodies that are published.

Every function takes a cursor rather than opening its own connection: post derivation runs
inside the caller's transaction, and a body minted for a post that then fails to write would
be a body nothing points at.
"""

# Until a jurisdiction has more than one body, every post lands here. The name is generic
# because the ocdid is: `…/place:berlin/government` says nothing about city vs township.
DEFAULT_ORGANIZATION_NAME = "Government"


async def find_or_create(
    cur, jurisdiction_ocdid: str, name: str = DEFAULT_ORGANIZATION_NAME
) -> str:
    await cur.execute(
        """
        INSERT INTO organizations (jurisdiction_ocdid, name)
        VALUES (%s, %s)
        ON CONFLICT (jurisdiction_ocdid, name) DO NOTHING
        RETURNING id::text
        """,
        (jurisdiction_ocdid, name),
    )
    inserted = await cur.fetchone()
    if inserted:
        return inserted[0]

    await cur.execute(
        "SELECT id::text FROM organizations WHERE jurisdiction_ocdid = %s AND name = %s",
        (jurisdiction_ocdid, name),
    )
    existing = await cur.fetchone()
    if existing is None:
        raise RuntimeError(
            f"organization {name!r} for {jurisdiction_ocdid} neither inserted nor found"
        )
    return existing[0]


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    await cur.execute(
        """
        SELECT id::text, name, sort_order
        FROM organizations
        WHERE jurisdiction_ocdid = %s
        ORDER BY sort_order, name
        """,
        (jurisdiction_ocdid,),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def find_or_create_for_changeset(cur, changeset_id: str, jurisdiction_ocdid: str) -> str:
    """The organization a changeset is about — found on the changeset, or created and written
    onto it the first time anything asks.

    Parallel to `find_or_create` above, and it writes for the same reason: the answer has to
    outlast the call, because the changeset is where "which body is this review about" belongs.

    A review is one organization at a time. `posts_identity_uq` is `(organization_id, role_id,
    division_ocdid)`, so the organization is the scope the rest of a post's identity sits inside.
    Callers used to work it out themselves with `find_or_create(jurisdiction)`, which is only
    right while a jurisdiction has one body.

    Writing it back is what makes the column converge: 158 backfilled every changeset whose
    jurisdiction already had an organization, and this fills the rest as they publish — the ones
    whose jurisdiction had never published anything at all.
    """
    await cur.execute(
        "SELECT organization_id::text FROM changesets WHERE id = %s",
        (changeset_id,),
    )
    row = await cur.fetchone()
    if row and row[0]:
        return row[0]

    organization_id = await find_or_create(cur, jurisdiction_ocdid)
    await cur.execute(
        "UPDATE changesets SET organization_id = %s WHERE id = %s",
        (organization_id, changeset_id),
    )
    return organization_id
