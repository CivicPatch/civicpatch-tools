import database.government_forms as government_forms_db
import database.organization_claims as organization_claims_db
from core.organization_build import FormOrganizationRow
from core.organization_derivation import role_labels_by_organization
from database.database import get_pool
from database.extras_organizations import get_extras_organizations
from shared.utils.government_forms import default_organization_name
from shared.utils.taxonomy import Taxonomy


async def ensure_defaults_exist(jurisdiction_ocdids: list[str]) -> None:
    """Give each jurisdiction with no organizations at all its first, default one, named
    `{lsad} Officers` from the jurisdiction's name.

    Called from the open-data sync as jurisdictions are upserted, so `get_default` never has to
    create one lazily afterward. Keyed on "has any organization", not on the name, so renaming
    the default does not bring a second one back on the next sync.
    """
    if not jurisdiction_ocdids:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, coalesce(data->>'name', '')
            FROM jurisdictions
            WHERE jurisdiction_ocdid = ANY(%s::text[])
              AND NOT EXISTS (
                SELECT 1 FROM organizations
                WHERE organizations.jurisdiction_ocdid = jurisdictions.jurisdiction_ocdid
              )
            """,
            (jurisdiction_ocdids,),
        )
        unbuilt = await cur.fetchall()
        if not unbuilt:
            return
        await cur.executemany(
            """
            INSERT INTO organizations (jurisdiction_ocdid, name, meta_is_default)
            VALUES (%s, %s, true)
            ON CONFLICT DO NOTHING
            """,
            [(ocdid, default_organization_name(name)) for ocdid, name in unbuilt],
        )


async def ensure_form_organizations(cur, rows: list[FormOrganizationRow]) -> int:
    """Create each organization its jurisdiction lacks. Never renames or deletes, so a person's own
    stays. Returns how many were created."""
    created = 0
    for row in rows:
        await cur.execute(
            """
            INSERT INTO organizations (jurisdiction_ocdid, name)
            VALUES (%s, %s)
            ON CONFLICT (jurisdiction_ocdid, name) DO NOTHING
            """,
            (row.jurisdiction_ocdid, row.name),
        )
        created += cur.rowcount
    return created


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


async def find_or_create(cur, jurisdiction_ocdid: str, name: str) -> str:
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


async def role_labels(cur, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> dict[str, dict[str, str]]:
    """Each organization's role id -> label, by its id: see `role_labels_by_name`."""
    names = await _names_by_id(cur, jurisdiction_ocdid)
    labels_by_name = await role_labels_by_name(cur, jurisdiction_ocdid, taxonomy)
    return {organization_id: labels_by_name.get(name, {}) for organization_id, name in names.items()}


async def role_labels_by_name(cur, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> dict[str, dict[str, str]]:
    """Each organization's role id -> label, by its name: its place's law, else its config form,
    then what people claimed about it."""
    answer = await get_extras_organizations(cur, jurisdiction_ocdid)
    government = await government_forms_db.get_resolved_government(jurisdiction_ocdid)
    names = await _names_by_id(cur, jurisdiction_ocdid)
    claimed = await organization_claims_db.claimed_roles(cur, list(names))
    claimed_by_name = {names[organization_id]: roles for organization_id, roles in claimed.items()}
    return role_labels_by_organization(answer, government.candidate_organizations, taxonomy, claimed_by_name)


async def _names_by_id(cur, jurisdiction_ocdid: str) -> dict[str, str]:
    await cur.execute("SELECT id::text, name FROM organizations WHERE jurisdiction_ocdid = %s", (jurisdiction_ocdid,))
    return {row[0]: row[1] for row in await cur.fetchall()}


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    by_jurisdiction = await list_for_jurisdictions(cur, [jurisdiction_ocdid])
    return by_jurisdiction.get(jurisdiction_ocdid, [])


async def list_for_jurisdictions(
    cur, jurisdiction_ocdids: list[str]
) -> dict[str, list[dict]]:
    await cur.execute(
        """
        SELECT jurisdiction_ocdid, id::text, name, url, sort_order, meta_is_default
        FROM organizations
        WHERE jurisdiction_ocdid = ANY(%s)
        ORDER BY sort_order, name
        """,
        (jurisdiction_ocdids,),
    )
    columns = [column.name for column in cur.description or []]
    by_jurisdiction: dict[str, list[dict]] = {}
    for row in await cur.fetchall():
        organization = dict(zip(columns, row))
        jurisdiction_ocdid = organization.pop("jurisdiction_ocdid")
        by_jurisdiction.setdefault(jurisdiction_ocdid, []).append(organization)
    return by_jurisdiction


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
        await cur.execute("UPDATE organizations SET name = %s, url = %s WHERE id = %s", (name, url, organization_id))
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


async def ids_with_source_records(cur, organization_ids: list[str]) -> set[str]:
    await cur.execute(
        "SELECT DISTINCT organization_id::text FROM source_records WHERE organization_id = ANY(%s::uuid[])",
        (organization_ids,),
    )
    return {row[0] for row in await cur.fetchall()}


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
