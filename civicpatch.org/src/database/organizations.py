"""Database queries for `organizations` — the body a post belongs to.

Every jurisdiction has a default organization unconditionally: migration 195 backfilled the
9,524 that predate it, and `services/sources/open_data.py` creates one the moment a jurisdiction
is synced in, active or not. `get_default` below relies on that — it looks up, it does not
create — so a jurisdiction with no organization is a bug in the sync path, not a normal case to
absorb quietly.

`find_or_create` still creates: a jurisdiction can also have named, non-default bodies (Council,
School Board) once something can tell them apart, and that path stays create-or-get.

Every function takes a cursor rather than opening its own connection, except `ensure_defaults_exist`
(no caller-held transaction at sync time): post derivation runs inside the caller's transaction,
and a body minted for a post that then fails to write would be a body nothing points at.
"""

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
        raise RuntimeError(f"jurisdiction {jurisdiction_ocdid!r} has no default organization")
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


async def for_changeset(cur, changeset_id: str) -> str | None:
    """The organization this changeset is about, or None if nothing has assigned one.

    Read-only, unlike `find_or_create_for_changeset` below: a caller that only needs the scope
    to *close* memberships must not mint a body as a side effect. None is not a gap — a
    jurisdiction with no organization has no posts, so it has no memberships to close either.
    """
    await cur.execute(
        "SELECT organization_id::text FROM changesets WHERE id = %s", (changeset_id,)
    )
    row = await cur.fetchone()
    return row[0] if row else None


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

    organization_id = await get_default(cur, jurisdiction_ocdid)
    await cur.execute(
        "UPDATE changesets SET organization_id = %s WHERE id = %s",
        (organization_id, changeset_id),
    )
    return organization_id
