"""Posts and the bodies they sit in — the roster screen's reads and writes.

Writes here are a person *declaring* a seat; the derivation's `find_or_create` is a scrape
*proposing* one. Same rows, and the difference only shows in who is allowed to change what:
`label` and `headcount` are reachable from here and from nowhere else.
"""

from core.post_grouping import group_by_organization
from database import divisions, organizations, posts
from database.database import get_pool


async def list_for_jurisdiction(jurisdiction_ocdid: str) -> list[dict]:
    """Every body in a jurisdiction with its posts. One connection, two reads."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_rows = await organizations.list_for_jurisdiction(
            cur, jurisdiction_ocdid
        )
        post_rows = await posts.list_for_jurisdiction(cur, jurisdiction_ocdid)
    return group_by_organization(organization_rows, post_rows)


async def create(
    jurisdiction_ocdid: str,
    role_id: str,
    division_ocdid: str,
    label: str | None,
    headcount: int,
) -> str | None:
    """A person asserting a seat exists. Returns its id, or None if it already did.

    Organization and division are found-or-created on the way through, exactly as the
    derivation does — a division exists because a post needs it, never on its own.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, jurisdiction_ocdid)
        await divisions.find_or_create(cur, division_ocdid, jurisdiction_ocdid)
        return await posts.create_if_absent(
            cur,
            jurisdiction_ocdid,
            organization_id,
            role_id,
            division_ocdid,
            label=label,
            headcount=headcount,
        )


async def update(post_id: str, label: str | None, headcount: int) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await posts.update_human_fields(cur, post_id, label, headcount)


async def delete(post_id: str) -> bool:
    """Remove a post nobody has held. False means it has members, or does not exist."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await posts.delete_if_unheld(cur, post_id)
