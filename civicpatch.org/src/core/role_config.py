import logging

import database.roles as db_roles
from schemas.jurisdictions import MergedRoleConfigResponse, RoleEntryData, RoleEntryWithSource, SetScopeRolesRequest
from shared.utils.config_utils import RoleConfig

logger = logging.getLogger(__name__)


async def load_role_config_per_level(ocdid: str) -> dict[str, RoleConfig]:
    """Read role config from the DB at each scope level for a given ocdid."""
    return await db_roles.get_role_config_per_level(ocdid)


def build_merged_response(per_level: dict[str, RoleConfig]) -> MergedRoleConfigResponse:
    seen: dict[str, RoleEntryWithSource] = {}
    for level in ("global", "state", "locality"):
        for entry in per_level.get(level, RoleConfig()).roles:
            seen[entry.role.lower()] = RoleEntryWithSource(
                role=entry.role,
                is_unique=entry.is_unique,
                aliases=entry.aliases,
                kind=entry.kind,
                source=level,
            )
    return MergedRoleConfigResponse(roles=list(seen.values()))


async def load_global_config() -> RoleConfig:
    """Read global roles + exclusions from the DB."""
    return await db_roles.get_global_config()


async def set_global_roles(entries: list[RoleEntryData], user_id: str | None = None) -> None:
    """Replace global roles + exclusions in the DB and write change_logs."""
    await db_roles.replace_roles_at_scope(None, entries, user_id)


async def set_scope_roles(req: SetScopeRolesRequest, user_id: str | None = None) -> None:
    """Replace scope-level roles + exclusions in the DB and write change_logs."""
    scope_ocdid = _scope_to_ocdid(req.scope, req.ocdid)
    await db_roles.replace_roles_at_scope(scope_ocdid, req.roles, user_id)


async def delete_role(role_value: str, scope: str, ocdid: str, user_id: str | None = None) -> None:
    """Hard-delete a role with no exclusion created."""
    scope_ocdid = _scope_to_ocdid(scope, ocdid)
    await db_roles.delete_role(role_value, scope_ocdid, user_id)


async def exclude_role(role_value: str, scope: str, ocdid: str, user_id: str | None = None) -> None:
    """Move a role to role_exclusions."""
    scope_ocdid = _scope_to_ocdid(scope, ocdid)
    await db_roles.exclude_role(role_value, scope_ocdid, user_id)


async def include_role(
    exclusion_value: str,
    scope: str,
    ocdid: str,
    user_id: str | None = None,
) -> None:
    """Move an exclusion back to canonical role. Aliases stay attached."""
    scope_ocdid = _scope_to_ocdid(scope, ocdid)
    await db_roles.include_role(exclusion_value, scope_ocdid, user_id)


def _scope_to_ocdid(scope: str, ocdid: str) -> str | None:
    """Derive the DB jurisdiction_ocdid from a scope + full ocdid pair.

    global → None (the DB sentinel for global scope)
    state  → state-level ocdid prefix (e.g. ocd-jurisdiction/country:us/state:tx)
    locality → the full ocdid as-is
    """
    if scope == "global":
        return None
    if scope == "state":
        parts = ocdid.split("/")
        for i, p in enumerate(parts):
            if p.startswith("state:"):
                return "/".join(parts[: i + 1])
        # Shouldn't happen for valid ocdids, but fall through to locality
    return ocdid


