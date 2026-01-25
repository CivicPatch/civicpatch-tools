import os
import yaml
from typing import Dict, List
from decimal import Decimal, InvalidOperation
from shared.schemas import JobConfig

_data_config = None
_divisions_config = None
_government_types_config = None
_crawl_config = None
_job_config = None

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_config_path():
    """
    Returns the absolute path to the configuration file.
    """
    config_path = os.path.join(ROOT_DIR, "config")

    return config_path

def get_data_config():
    global _data_config
    if _data_config is None:
        config_path = get_config_path()
        data_file_path = os.path.join(config_path, 'data.yml')
        with open(data_file_path, 'r') as config_file:
            config_data = yaml.safe_load(config_file)
        _data_config = config_data.get('data', {})
    return _data_config

def get_divisions():
    global _divisions_config
    if _divisions_config is None:
        config_path = get_config_path()
        divisions_file_path = os.path.join(config_path, 'divisions.yml')
        with open(divisions_file_path, 'r') as config_file:
            config_data = yaml.safe_load(config_file)
        _divisions_config = config_data.get('divisions', {})
    return _divisions_config

def get_division_names() -> List[str]:
    """
    Returns a list of canonical division names from the configuration file.
    """
    divisions_config = get_divisions()
    return list(divisions_config.keys())

def get_division_alias_map() -> Dict[str, str]:
    """
    Build a mapping from all aliases to their canonical division type.
    """
    divisions_config = get_divisions()

    alias_map = {}
    for canonical, entry in divisions_config.items():
        alias_map[canonical.lower()] = canonical
        for alias in entry.get("aliases", []):
            alias_map[alias.lower()] = canonical
    return alias_map

def get_government_types():
    global _government_types_config
    if _government_types_config is None:
        config_path = get_config_path()
        government_types_file_path = os.path.join(config_path, 'government_types.yml')
        with open(government_types_file_path, 'r') as config_file:
            config_data = yaml.safe_load(config_file)
        _government_types_config = config_data.get('government_types', {})
    return _government_types_config

def get_roles_by_government_type(government_type: str) -> List[str]:
    """
    Returns a list of roles associated with a specific government type from the configuration file.
    
    Args:
        government_type: The type of government (e.g., "mayor_council", "commission").
    
    Returns:
        List of roles associated with the specified government type.
    """
    government_types = get_government_types()
    role_configs = government_types.get(government_type, {}).get('roles', [])
    return [role['role'] for role in role_configs]

def get_all_roles_by_government_type(government_type: str) -> List[str]:
    """
    Returns a list of all roles and their aliases associated with a specific government type from the configuration file.
    """
    government_types = get_government_types()
    role_configs = government_types.get(government_type, {}).get('roles', [])
    roles = []
    for role in role_configs:
        roles.append(role['role'])
        roles.extend(role.get('aliases', []))
    return roles

def get_head_of_government_role(government_type: str) -> str:
    """
    Returns the head of government role for a specific government type from the configuration file.
    
    Args:
        government_type: The type of government (e.g., "mayor_council", "commission").
    
    Returns:
        The head of government role associated with the specified government type.
    """
    government_types = get_government_types()
    return government_types.get(government_type, {}).get('head_of_government', '')

def get_role_configs_by_government_type(government_type: str) -> List[Dict[str, List[str]]]:
    """
    Returns a list of role configurations associated with a specific government type from the configuration file.
    """
    government_types = get_government_types()
    roles = government_types.get(government_type, {}).get('roles', [])

    # Ensure each role is a dictionary with a string `role` and a list `aliases`
    normalized_roles = []
    for role_entry in roles:
        if isinstance(role_entry, dict):
            normalized_roles.append(role_entry)
        elif isinstance(role_entry, str):
            normalized_roles.append({"role": role_entry, "aliases": []})

    return normalized_roles

def get_unique_roles(government_type: str) -> List[str]:
    """
    Returns a list of roles marked as unique for a specific government type from the configuration file.
    """
    role_configs = get_role_configs_by_government_type(government_type)
    unique_roles = [entry['role'] for entry in role_configs if entry.get('is_unique', False)]
    return unique_roles

def get_crawl():
    global _crawl_config
    if _crawl_config is None:
        config_path = get_config_path()
        crawl_file_path = os.path.join(config_path, 'crawl.yml')
        with open(crawl_file_path, 'r') as config_file:
            _crawl_config = yaml.safe_load(config_file)
    return _crawl_config

def search_keywords(government_type: str) -> Dict[str, List[str]]:
    """
    Returns the search keywords from the configuration file.
    """
    config_path = get_config_path()
    government_types_file_path = os.path.join(config_path, 'government_types.yml')
    with open(government_types_file_path, 'r') as config_file:
        config = yaml.safe_load(config_file)
        government_types_config = config.get('government_types', {})

    government_type_config = government_types_config.get(government_type, {})
    return government_type_config.get('keywords', [])

def get_job_config(logger) -> JobConfig:
    # You can override certain properties
    global _job_config
    if _job_config is None:
        config_path = get_config_path()
        process_file_path = os.path.join(config_path, 'workflow.yml')
        with open(process_file_path, 'r') as config_file:
            _job_config = yaml.safe_load(config_file)

    if os.getenv("PIPELINE_RUN_COST_LIMIT"):
        try:
            pipeline_run_cost_limit_string = os.getenv("PIPELINE_RUN_COST_LIMIT")
            if pipeline_run_cost_limit_string:
                logger.info(f"Overriding pipeline_run_cost_limit with environment variable: {pipeline_run_cost_limit_string}")
                pipeline_run_cost_limit = Decimal(pipeline_run_cost_limit_string)
                _job_config['pipeline_run_cost_limit'] = pipeline_run_cost_limit
        except (ValueError, InvalidOperation):
            pass
    return JobConfig(
        max_pages=_job_config.get('max_pages'),
        pipeline_run_cost_limit=_job_config.get('pipeline_run_cost_limit')
    )

def get_role_alias_map(government_type: str) -> Dict[str, str]:
    role_configs = get_role_configs_by_government_type(government_type)
    alias_map = {}

    for entry in role_configs:
        role_entry = entry.get("role", "")
        canonical_role = role_entry if isinstance(role_entry, str) else " ".join(role_entry).strip()
        if not canonical_role:
            continue

        # Add the canonical role to the alias map (case-insensitive)
        alias_map[canonical_role.lower()] = canonical_role

        # Add each alias to the alias map, pointing to the canonical role
        aliases = entry.get("aliases", [])
        for alias in aliases:
            alias_map[alias.lower()] = canonical_role

    return alias_map

def get_context_keywords(government_type: str) -> List[str]:
    """
    Combines all search keywords (including roles and divisions and their aliases)
    into a single list.
    """
    government_types = get_government_types()
    keywords = set()
    # Add all keys and values under search_keywords
    search_keywords = government_types.get(government_type, {}).get('search_keywords', {})
    for key, values in search_keywords.items():
        keywords.add(key)
        keywords.update(values)

    # Add all roles and their aliases
    role_configs = government_types.get(government_type, {}).get('roles', [])
    for role in role_configs:
        keywords.add(role['role'])
        for alias in role.get('aliases', []):
            keywords.add(alias)

    # Add all divisions and their aliases
    divisions_config = get_divisions()
    for canonical, entry in divisions_config.items():
        keywords.add(canonical)
        for alias in entry.get('aliases', []):
            keywords.add(alias)

    ## Extra keywords for content filtering
    extra_keywords = ["title", "email", "phone", "contact", "address",
                      "start date", "elected at", "end date", "term expires",
                      "current term"]
    keywords.update(extra_keywords)

    return list(keywords)