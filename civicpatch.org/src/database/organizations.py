from database.database import get_pool

# Until a jurisdiction has more than one body, every post lands here. The name is generic
# because the ocdid is: `…/place:berlin/government` says nothing about city vs township.
DEFAULT_ORGANIZATION_NAME = "Government"


async def ensure_defaults_exist(jurisdiction_ocdids: list[str]) -> None:
    """Create each jurisdiction's default organization if it doesn't already have one.

    Called from the open-data sync as jurisdictions are upserted, so `get_default` never has to
    create one lazily afterward.
    """
    if not jurisdiction_ocdids:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO organizations (jurisdiction_ocdid, name)
            VALUES (%s, %s)
            ON CONFLICT (jurisdiction_ocdid, name) DO NOTHING
            """,
            [(ocdid, DEFAULT_ORGANIZATION_NAME) for ocdid in jurisdiction_ocdids],
        )


async def get_default(cur, jurisdiction_ocdid: str) -> str:
    """The jurisdiction's default organization. Guaranteed to exist — see module docstring."""
    await cur.execute(
        "SELECT id::text FROM organizations WHERE jurisdiction_ocdid = %s AND name = %s",
        (jurisdiction_ocdid, DEFAULT_ORGANIZATION_NAME),
    )
    row = await cur.fetchone()
    if row is None:
        raise RuntimeError(
            f"jurisdiction {jurisdiction_ocdid!r} has no default organization"
        )
    return row[0]


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


async def jurisdiction_for(cur, organization_id: str) -> str | None:
    await cur.execute(
        "SELECT jurisdiction_ocdid FROM organizations WHERE id = %s", (organization_id,)
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    await cur.execute(
        """
        SELECT id::text, name, url, sort_order
        FROM organizations
        WHERE jurisdiction_ocdid = %s
        ORDER BY sort_order, name
        """,
        (jurisdiction_ocdid,),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def create(jurisdiction_ocdid: str, name: str, url: str | None) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO organizations (jurisdiction_ocdid, name, url)
            VALUES (%s, %s, %s)
            ON CONFLICT (jurisdiction_ocdid, name) DO NOTHING
            RETURNING id::text
            """,
            (jurisdiction_ocdid, name, url),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def update(organization_id: str, name: str, url: str | None) -> bool:
    """False if no such organization."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE organizations SET name = %s, url = %s WHERE id = %s",
            (name, url, organization_id),
        )
        return cur.rowcount > 0


async def delete(organization_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid, name FROM organizations WHERE id = %s",
            (organization_id,),
        )
        row = await cur.fetchone()
        if row is None or row[1] == DEFAULT_ORGANIZATION_NAME:
            return None
        await cur.execute(
            "SELECT 1 FROM posts WHERE organization_id = %s LIMIT 1", (organization_id,)
        )
        if await cur.fetchone():
            return None
        await cur.execute("DELETE FROM organizations WHERE id = %s", (organization_id,))
        return row[0]


async def for_changeset(cur, changeset_id: str) -> str | None:
    await cur.execute(
        "SELECT organization_id::text FROM changesets WHERE id = %s", (changeset_id,)
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def find_or_create_for_changeset(
    cur, changeset_id: str, jurisdiction_ocdid: str
) -> str:
    await cur.execute(
        "SELECT organization_id::text FROM changesets WHERE id = %s",
        (changeset_id,),
    )
    row = await cur.fetchone()
    if row and row[0]:
        return row[0]

    organization_id = await get_default(cur, jurisdiction_ocdid)
    await cur.execute(
        "UPDATE changesets SET organization_id = %s WHERE id = %s",
        (organization_id, changeset_id),
    )
    return organization_id
