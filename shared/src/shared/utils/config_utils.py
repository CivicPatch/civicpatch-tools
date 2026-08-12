import os
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, List, Optional

import yaml
from pydantic import BaseModel
from shared.schemas import JobConfig
from shared.utils.id_utils import jurisdiction_ocdid_to_folder


class RoleEntry(BaseModel):
    role: str
    is_unique: bool = False
    aliases: List[str] = []


class RoleConfig(BaseModel):
    roles: List[RoleEntry] = []


# In-memory cache for config files
_config_cache = {}

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_path():
    return os.path.join(ROOT_DIR, "config")


def _load_config_file(filename: str, key: str = None, default=None):
    cache_key = (filename, key)
    if cache_key in _config_cache:
        return _config_cache[cache_key]
    file_path = os.path.join(get_config_path(), filename)
    with open(file_path, "r") as config_file:
        config_data = yaml.safe_load(config_file)
    result = config_data if key is None else config_data.get(key, default)
    _config_cache[cache_key] = result
    return result


def get_data_config():
    return _load_config_file("data.yml", "data", {})


def get_role_configs(
    role_config_override: Optional[RoleConfig] = None,
) -> List[RoleEntry]:
    if role_config_override is not None:
        return [entry for entry in role_config_override.roles]
    return []


def get_designations():
    return _load_config_file("designations.yml", "designations", {})


def get_role_names(role_config_override: Optional[RoleConfig] = None) -> List[str]:
    names = []
    for entry in get_role_configs(role_config_override):
        names.append(entry.role)
        names.extend(entry.aliases)
    return names


def get_designation_names() -> List[str]:
    return list(get_designations().keys())


def get_designation_alias_map() -> Dict[str, str]:
    alias_map = {}
    for canonical, entry in get_designations().items():
        alias_map[canonical.lower()] = canonical
        for alias in entry.get("aliases", []):
            alias_map[alias.lower()] = canonical
    return alias_map


def get_unique_roles(role_config_override: Optional[RoleConfig] = None) -> List[str]:
    return [
        entry.role
        for entry in get_role_configs(role_config_override)
        if entry.is_unique
    ]


def search_keywords(type="local") -> Dict[str, List[str]]:
    return _load_config_file("search.yml").get("keywords", {})


def governance_keywords() -> List[str]:
    return _load_config_file("keywords.yml", "keywords", [])


def load_job_config(logger=None) -> JobConfig:
    config = _load_config_file("pipeline.yml")
    if os.getenv("PIPELINE_RUN_COST_LIMIT"):
        try:
            pipeline_run_cost_limit_string = os.getenv("PIPELINE_RUN_COST_LIMIT")
            if pipeline_run_cost_limit_string:
                if logger is not None:
                    logger.info(
                        f"Overriding pipeline_run_cost_limit with environment variable: {pipeline_run_cost_limit_string}"
                    )
                pipeline_run_cost_limit = Decimal(pipeline_run_cost_limit_string)
                config["pipeline_run_cost_limit"] = pipeline_run_cost_limit
        except (ValueError, InvalidOperation):
            pass
    return JobConfig(
        max_pages=config.get("max_pages"),
        pipeline_run_cost_limit=config.get("pipeline_run_cost_limit"),
    )


def get_role_alias_map(
    role_config_override: Optional[RoleConfig] = None,
) -> Dict[str, str]:
    alias_map = {}
    for entry in get_role_configs(role_config_override):
        alias_map[entry.role.lower()] = entry.role
        for alias in entry.aliases:
            alias_map[alias.lower()] = entry.role
    return alias_map


def get_keywords() -> List[str]:
    role_keywords = set(get_role_alias_map().keys()) | set(
        get_role_alias_map().values()
    )
    designation_keywords = set(get_designation_alias_map().keys()) | set(
        get_designation_alias_map().values()
    )
    extra_keywords = [
        "title",
        "email",
        "phone",
        "contact",
        "address",
        "start date",
        "elected at",
        "end date",
        "term expires",
        "current term",
        "committee",
        "board",
        "township",
        "village",
        "city",
    ]
    return list(
        role_keywords
        | designation_keywords
        | set(governance_keywords())
        | set(extra_keywords)
    )


def merge_role_configs(*configs: RoleConfig) -> RoleConfig:
    roles: Dict[str, RoleEntry] = {}
    for cfg in configs:
        for entry in cfg.roles:
            roles[entry.role.lower()] = entry
    return RoleConfig(roles=list(roles.values()))


def load_role_config_for_jurisdiction(
    jurisdiction_ocdid: str,
    fetch_remote: Callable[[str], Optional[str]],
) -> RoleConfig:
    folder = jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    state, output_type, locality = folder.split("/")
    paths = [
        f"data_source/{output_type}/config.yml",
        f"data_source/{state}/config.yml",
        f"data_source/{state}/{output_type}/config.yml",
        f"data_source/{state}/{output_type}/{locality}/config.yml",
    ]
    configs = []
    for path in paths:
        raw = fetch_remote(path)
        if raw is not None:
            configs.append(RoleConfig.model_validate(yaml.safe_load(raw)))
    return merge_role_configs(*configs)
