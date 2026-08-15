import os
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

import yaml
from shared.schemas import JobConfig, RoleConfig, Role, RoleStatus

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
) -> List[Role]:
    """Only `active` roles. Every taxonomy consumer funnels through here, so
    this is the one place that decides what the matcher can see.

    `inactive` is a removed role. `excluded` and `candidate` are matchable by
    design — excluded so a known non-role label can be knowingly dropped,
    candidate so triage has something to show — but neither path exists yet, and
    treating them as ordinary roles (which is what happened before this filter)
    is worse than not matching them at all.
    """
    if role_config_override is None:
        return []
    return [
        entry for entry in role_config_override.roles
        if entry.status == RoleStatus.ACTIVE
    ]


def get_excluded_role_aliases(
    role_config_override: Optional[RoleConfig] = None,
) -> List[str]:
    """Labels and aliases of `excluded` roles — terms a matcher must recognize precisely so
    it can knowingly drop them.

    Deliberately separate from `get_role_configs`, which decides what may be matched *as a
    role*. An excluded term must never resolve to one; it must resolve to nothing at all,
    which is a different answer from "unknown". Unknown labels are passed through verbatim
    so a genuinely new role is not lost, and that fallback is exactly what an exclusion has
    to bypass.
    """
    if role_config_override is None:
        return []
    names = []
    for entry in role_config_override.roles:
        if entry.status != RoleStatus.EXCLUDED:
            continue
        names.append(entry.label)
        names.extend(entry.aliases)
    return names


def get_designations():
    return _load_config_file("designations.yml", "designations", {})


def get_role_names(role_config_override: Optional[RoleConfig] = None) -> List[str]:
    names = []
    for entry in get_role_configs(role_config_override):
        names.append(entry.label)
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
        entry.label for entry in get_role_configs(role_config_override) if entry.is_unique
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
        alias_map[entry.label.lower()] = entry.label
        for alias in entry.aliases:
            alias_map[alias.lower()] = entry.label
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
