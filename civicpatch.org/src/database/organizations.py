from database.database import get_pool

# The name a jurisdiction's first body is created with. Generic because the ocdid is:
# `…/place:berlin/government` says nothing about city vs township. Only a starting name —
# which body is the default is `meta_is_default`, so this one can be renamed.
DEFAULT_ORGANIZATION_NAME = "Government"


async def ensure_defaults_exist(jurisdiction_ocdids: list[str]) -> None:
    """Give each jurisdiction with no organizations at all its first, default one.

    Called from the open-data sync as jurisdictions are upserted, so `get_default` never has to
    create one lazily afterward. Keyed on "has any organization", not on the name, so renaming
    the default does not bring a second 'Government' back on the next sync.
    """
    if not jurisdiction_ocdids:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO organizations (jurisdiction_ocdid, name, meta_is_default)
            SELECT ocdid, %s, true
            FROM unnest(%s::text[]) AS ocdid
            WHERE NOT EXISTS (
                SELECT 1 FROM organizations WHERE organizations.jurisdiction_ocdid = ocdid
            )
            ON CONFLICT DO NOTHING
            """,
            (DEFAULT_ORGANIZATION_NAME, jurisdiction_ocdids),
        )


async def get_default(cur, jurisdiction_ocdid: str) -> str:
    """The flagged organization, else the first in list order."""
    await cur.execute(
        """
        SELECT id::text FROM organizations
        WHERE jurisdiction_ocdid = %s
        ORDER BY meta_is_default DESC, sort_order, name
        LIMIT 1
        """,
        (jurisdiction_ocdid,),
    )
    row = await cur.fetchone()
    if row is None:
        raise RuntimeError(
            f"jurisdiction {jurisdiction_ocdid!r} has no organizations"
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


async def names(cur, organization_ids: list[str]) -> dict[str, str]:
    await cur.execute(
        "SELECT id::text, name FROM organizations WHERE id::text = ANY(%s)", (organization_ids,)
    )
    return {row[0]: row[1] for row in await cur.fetchall()}


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    await cur.execute(
        """
        SELECT id::text, name, url, sort_order, meta_is_default
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


async def set_default(organization_id: str) -> bool:
    """False if no such organization."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        jurisdiction_ocdid = await jurisdiction_for(cur, organization_id)
        if jurisdiction_ocdid is None:
            return False
        # Two concurrent calls would otherwise race into the one-default unique index.
        await cur.execute(
            "SELECT 1 FROM organizations WHERE jurisdiction_ocdid = %s FOR UPDATE",
            (jurisdiction_ocdid,),
        )
        await cur.execute(
            "UPDATE organizations SET meta_is_default = false "
            "WHERE jurisdiction_ocdid = %s AND meta_is_default AND id <> %s",
            (jurisdiction_ocdid, organization_id),
        )
        await cur.execute(
            "UPDATE organizations SET meta_is_default = true WHERE id = %s", (organization_id,)
        )
        return True


async def delete(organization_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        jurisdiction_ocdid = await jurisdiction_for(cur, organization_id)
        if jurisdiction_ocdid is None:
            return None
        default_organization_id = await get_default(cur, jurisdiction_ocdid)
        if default_organization_id == organization_id:
            return None
        await cur.execute(
            "SELECT 1 FROM posts WHERE organization_id = %s LIMIT 1", (organization_id,)
        )
        if await cur.fetchone():
            return None
        await cur.execute(
            "UPDATE source_records SET organization_id = %s WHERE organization_id = %s",
            (default_organization_id, organization_id),
        )
        await cur.execute("DELETE FROM organizations WHERE id = %s", (organization_id,))
        return jurisdiction_ocdid


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
