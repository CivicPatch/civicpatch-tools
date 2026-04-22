import logging

import lib.github.api as github_service
from schemas.jurisdictions import MergedRoleConfigResponse, RoleEntryWithSource, SetScopeRolesRequest
from shared.utils.config_utils import RoleConfig, RoleEntry
from shared.utils.id_utils import jurisdiction_ocdid_to_folder
from shared.utils.yaml_utils import yaml_dump, yaml_load

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


async def _write_once(path: str, content: str, commit_message: str) -> bool:
    return await github_service.upsert_github_file(
        branch_name="main",
        file_path=path,
        content_str=content,
        commit_message=commit_message,
    )


async def set_scope_roles(req: SetScopeRolesRequest) -> None:
    folder = jurisdiction_ocdid_to_folder(req.ocdid)
    path, content = await build_updated_config(req)
    commit_message = f"Update {req.scope} roles for {folder}"
    if await _write_once(path, content, commit_message):
        return
    if not await _write_once(path, content, commit_message):
        raise RuntimeError("Failed to write role config after retry (SHA conflict)")
