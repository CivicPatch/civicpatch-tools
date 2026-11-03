"""Reads of the role taxonomy (roles). Roles are edited in open-data's config files, and the
post-merge sync writes `roles` (`database.jurisdiction_configs`). `id` is a slug ("council-member"), immutable once
minted; removal is `status='inactive'`, nothing is hard-deleted.
"""

from database.database import get_pool
from database.jurisdiction_configs import get_jurisdiction_configs
from shared.schemas import Role, RoleAliasStatus, RoleConfig
from shared.utils.layered_config import jurisdiction_roles
from shared.utils.taxonomy import Taxonomy, build_taxonomy


async def _fetch_roles(cur) -> list[Role]:
    """Every role with only its *approved* aliases — a candidate alias must not
    reach the matcher."""
    await cur.execute(
        """
        SELECT r.id, r.label, r.status, r.is_unique, r.priority, r.selection_method,
               COALESCE(
                   array_agg(a.label ORDER BY a.label) FILTER (WHERE a.id IS NOT NULL),
                   '{}'
               )
        FROM roles r
        LEFT JOIN role_aliases a ON a.role_id = r.id AND a.status = %s
        GROUP BY r.id, r.label, r.status, r.is_unique, r.priority, r.selection_method
        ORDER BY r.priority NULLS LAST, r.label
        """,
        (RoleAliasStatus.ACTIVE,),
    )
    return [
        Role(
            id=id,
            label=label,
            status=status,
            is_unique=is_unique,
            priority=priority,
            selection_method=selection_method,
            aliases=aliases,
        )
        for id, label, status, is_unique, priority, selection_method, aliases in await cur.fetchall()
    ]


async def get_role(cur, role_id: str) -> Role | None:
    """One role by id, or None. Aliases come back empty — callers wanting those want the
    whole taxonomy, not a single row."""
    await cur.execute(
        "SELECT id, label, status, is_unique, priority, selection_method FROM roles WHERE id = %s",
        (role_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    id, label, status, is_unique, priority, selection_method = row
    return Role(
        id=id, label=label, status=status, is_unique=is_unique, priority=priority, selection_method=selection_method
    )


async def get_roles() -> list[Role]:
    """Every role, ordered.

    Inactive roles are included: filtering those is the caller's
    decision, since the admin UI needs to see them and the pipeline does not.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await _fetch_roles(cur)


async def get_taxonomy_for(jurisdiction_ocdid: str) -> Taxonomy:
    """The taxonomy of the jurisdiction's level and state, from the stored config files."""
    return _taxonomy(jurisdiction_roles(await get_jurisdiction_configs(), jurisdiction_ocdid))


async def get_taxonomies_for(jurisdiction_ocdids: list[str]) -> dict[str, Taxonomy]:
    """`get_taxonomy_for` for many jurisdictions, reading the config files once."""
    configs = await get_jurisdiction_configs()
    return {ocdid: _taxonomy(jurisdiction_roles(configs, ocdid)) for ocdid in jurisdiction_ocdids}


def _taxonomy(roles: list[Role]) -> Taxonomy:
    return build_taxonomy(RoleConfig(roles=roles))
