import logging

import database.roles as db_roles
from schemas.roles import RoleInput
from shared.schemas import Role

logger = logging.getLogger(__name__)


async def load_roles() -> list[Role]:
    return await db_roles.get_roles()


async def set_roles(entries: list[RoleInput], user_id: str | None = None) -> None:
    """Add or update the submitted roles and write change_logs.

    Absence is not removal — see `db_roles.upsert_roles`. Removal is
    `deactivate_role`.
    """
    await db_roles.upsert_roles(entries, user_id)


async def reorder_roles(
    role_order: list[str],
    moved_roles: list[str] | None = None,
    user_id: str | None = None,
) -> None:
    """Set canonical role priority by position."""
    await db_roles.reorder_roles(role_order, user_id, moved_roles)


async def deactivate_role(role_id: str, user_id: str | None = None) -> bool:
    """Deactivate a role. Returns False if it does not exist or was already inactive."""
    return await db_roles.deactivate_role(role_id, user_id)
