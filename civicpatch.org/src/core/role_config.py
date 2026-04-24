import logging

import lib.github.api as github_service
from schemas.jurisdictions import MergedRoleConfigResponse, RoleEntryWithSource, SetScopeRolesRequest
from shared.utils.config_utils import RoleConfig, RoleEntry
from shared.utils.id_utils import jurisdiction_ocdid_to_folder
from shared.utils.yaml_utils import yaml_dump, yaml_load

_GLOBAL_CONFIG_PATH = "data_source/local/config.yml"

logger = logging.getLogger(__name__)


def _scope_path(scope: str, folder: str) -> str:
    state, output_type, locality = folder.split("/")
    if scope == "global":
        return f"data_source/{output_type}/config.yml"
    if scope == "state":
        return f"data_source/{state}/{output_type}/config.yml"
    return f"data_source/{state}/{output_type}/{locality}/config.yml"


async def load_role_config_per_level(ocdid: str) -> dict[str, RoleConfig]:
    folder = jurisdiction_ocdid_to_folder(ocdid)
    levels = {
        "global": _scope_path("global", folder),
        "state": _scope_path("state", folder),
        "locality": _scope_path("locality", folder),
    }
    result = {}
    for level, path in levels.items():
        raw = await github_service.get_github_file_contents(path)
        result[level] = RoleConfig.model_validate(yaml_load(raw)) if raw else RoleConfig()
    return result


def build_merged_response(per_level: dict[str, RoleConfig]) -> MergedRoleConfigResponse:
    seen: dict[str, RoleEntryWithSource] = {}
    for level in ("global", "state", "locality"):
        for entry in per_level.get(level, RoleConfig()).roles:
            seen[entry.role.lower()] = RoleEntryWithSource(
                role=entry.role,
                is_unique=entry.is_unique,
                aliases=entry.aliases,
                source=level,
            )
    return MergedRoleConfigResponse(roles=list(seen.values()))


async def build_updated_config(req: SetScopeRolesRequest) -> tuple[str, str]:
    folder = jurisdiction_ocdid_to_folder(req.ocdid)
    path = _scope_path(req.scope, folder)
    raw = await github_service.get_github_file_contents(path)
    existing = RoleConfig.model_validate(yaml_load(raw)) if raw else RoleConfig()
    updated = RoleConfig(
        roles=[RoleEntry(role=r.role, is_unique=r.is_unique, aliases=r.aliases) for r in req.roles],
        excluded_roles=existing.excluded_roles,
    )
    return path, yaml_dump(updated.model_dump())


def _describe_role_changes(old: RoleConfig, new_roles: list, scope_label: str) -> str:
    old_by_name = {r.role.lower(): r for r in old.roles}
    new_by_name = {r.role.lower(): r for r in new_roles}
    added = [r for k, r in new_by_name.items() if k not in old_by_name]
    removed = [r for k, r in old_by_name.items() if k not in new_by_name]
    updated = [r for k, r in new_by_name.items() if k in old_by_name and (
        r.is_unique != old_by_name[k].is_unique or r.aliases != old_by_name[k].aliases or r.role != old_by_name[k].role
    )]
    parts = []
    if len(added) == 1 and not removed and not updated:
        return f"Add {scope_label} role '{added[0].role}'"
    if len(removed) == 1 and not added and not updated:
        return f"Remove {scope_label} role '{removed[0].role}'"
    if len(updated) == 1 and not added and not removed:
        return f"Update {scope_label} role '{updated[0].role}'"
    if added:
        parts.append("add " + ", ".join(f"'{r.role}'" for r in added))
    if removed:
        parts.append("remove " + ", ".join(f"'{r.role}'" for r in removed))
    if updated:
        parts.append("update " + ", ".join(f"'{r.role}'" for r in updated))
    return f"Update {scope_label} config: {'; '.join(parts)}" if parts else f"Update {scope_label} config"


async def _write_once(path: str, content: str, commit_message: str, author: dict | None = None) -> bool:
    return await github_service.upsert_github_file(
        branch_name="main",
        file_path=path,
        content_str=content,
        commit_message=commit_message,
        author=author,
    )

async def load_global_config() -> RoleConfig:
    raw = await github_service.get_github_file_contents(_GLOBAL_CONFIG_PATH)
    return RoleConfig.model_validate(yaml_load(raw)) if raw else RoleConfig()


async def set_global_roles(roles: list, author: dict | None = None) -> None:
    raw = await github_service.get_github_file_contents(_GLOBAL_CONFIG_PATH)
    existing = RoleConfig.model_validate(yaml_load(raw)) if raw else RoleConfig()
    new_entries = [RoleEntry(role=r.role, is_unique=r.is_unique, aliases=r.aliases) for r in roles]
    updated = RoleConfig(roles=new_entries, excluded_roles=existing.excluded_roles)
    commit_message = _describe_role_changes(existing, new_entries, "global")
    content = yaml_dump(updated.model_dump())
    if not await _write_once(_GLOBAL_CONFIG_PATH, content, commit_message, author):
        if not await _write_once(_GLOBAL_CONFIG_PATH, content, commit_message, author):
            raise RuntimeError("Failed to write global role config after retry (SHA conflict)")


async def set_scope_roles(req: SetScopeRolesRequest, author: dict | None = None) -> None:
    folder = jurisdiction_ocdid_to_folder(req.ocdid)
    parts = folder.split("/")
    state = parts[0].upper() if parts else ""
    if req.scope == "state":
        scope_label = f"{state} state"
    elif req.scope == "locality" and len(parts) >= 3:
        scope_label = f"{state} locality"
    else:
        scope_label = req.scope
    path = _scope_path(req.scope, folder)
    raw = await github_service.get_github_file_contents(path)
    existing = RoleConfig.model_validate(yaml_load(raw)) if raw else RoleConfig()
    new_entries = [RoleEntry(role=r.role, is_unique=r.is_unique, aliases=r.aliases) for r in req.roles]
    updated = RoleConfig(roles=new_entries, excluded_roles=existing.excluded_roles)
    commit_message = _describe_role_changes(existing, new_entries, scope_label)
    content = yaml_dump(updated.model_dump())
    if await _write_once(path, content, commit_message, author):
        return
    if not await _write_once(path, content, commit_message, author):
        raise RuntimeError("Failed to write role config after retry (SHA conflict)")
