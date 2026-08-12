import logging

import database.roles as db_roles
from schemas.jurisdictions import (
    MergedRoleConfigResponse,
    RoleDefinition,
    ScopedRole,
    SetScopeRolesRequest,
)
from shared.schemas import RoleConfig

logger = logging.getLogger(__name__)

SCOPE_ORDER = ("global", "state", "locality")


async def load_role_config_per_level(ocdid: str) -> dict[str, RoleConfig]:
    """Read role config from the DB at each scope level for a given ocdid."""
    return await db_roles.get_role_config_per_level(ocdid)


def build_merged_response(per_level: dict[str, RoleConfig]) -> MergedRoleConfigResponse:
    seen: dict[str, ScopedRole] = {}
    for level in SCOPE_ORDER:
        for entry in per_level.get(level, RoleConfig()).roles:
            seen[entry.role.lower()] = ScopedRole(
                role=entry.role,
                is_unique=entry.is_unique,
                aliases=entry.aliases,
                scope=level,
            )
    return MergedRoleConfigResponse(roles=list(seen.values()))


async def load_global_config() -> RoleConfig:
    """Read global roles from the DB."""
    return await db_roles.get_global_config()


async def set_global_roles(
    entries: list[RoleDefinition], user_id: str | None = None
) -> None:
    """Replace global roles in the DB and write change_logs."""
    await db_roles.replace_roles_at_scope(None, entries, user_id)


async def set_scope_roles(
    req: SetScopeRolesRequest, user_id: str | None = None
) -> None:
    """Replace scope-level roles in the DB and write change_logs."""
    scope_ocdid = _scope_to_ocdid(req.scope, req.ocdid)
    await db_roles.replace_roles_at_scope(scope_ocdid, req.roles, user_id)


async def reorder_roles(
    scope: str,
    ocdid: str | None,
    role_order: list[str],
    moved_roles: list[str] | None = None,
    user_id: str | None = None,
) -> None:
    """Set canonical role priority by position for a scope (global/state/locality)."""
    scope_ocdid = _scope_to_ocdid(scope, ocdid or "")
    await db_roles.reorder_roles_at_scope(scope_ocdid, role_order, user_id, moved_roles)


async def delete_role(
    role_value: str, scope: str, ocdid: str, user_id: str | None = None
) -> None:
    """Hard-delete a role."""
    scope_ocdid = _scope_to_ocdid(scope, ocdid)
    await db_roles.delete_role(role_value, scope_ocdid, user_id)


def _scope_to_ocdid(scope: str, ocdid: str) -> str | None:
    """Derive the DB jurisdiction_ocdid from a scope + full ocdid pair.

    Produces full OCDIDs that round-trip through parse_jurisdiction_ocdid —
    state/county scope keys include the jurisdiction_type suffix (e.g.
    `/government`), not just the prefix.

    global   → None (DB sentinel for global scope)
    state    → ocd-jurisdiction/country:us/state:tx/government
    county   → ocd-jurisdiction/country:us/state:tx/county:travis/government
    locality → the full ocdid as-is
    """
    if scope == "global":
        return None
    if scope in ("state", "county"):
        prefix = "state:" if scope == "state" else "county:"
        parts = ocdid.split("/")
        for i, p in enumerate(parts):
            if p.startswith(prefix):
                return "/".join(parts[: i + 1] + [parts[-1]])
        # Shouldn't happen for valid ocdids, but fall through to locality
    return ocdid
