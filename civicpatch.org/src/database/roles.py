"""Reads of the role taxonomy (roles). Writes go through open-data's config file: a Role Taxonomy
edit opens a pull request (`services.role_config_pull_request`), and the post-merge sync writes
`roles` (`database.jurisdiction_configs`). `id` is a slug ("council-member"), immutable once
minted; removal is `status='inactive'`, nothing is hard-deleted.
"""

from database.database import get_pool
from shared.schemas import Role, RoleAliasStatus


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
