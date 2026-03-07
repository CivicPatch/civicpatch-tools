import os
import yaml
from typing import Dict, List
from decimal import Decimal, InvalidOperation
from shared.schemas import JobConfig

# In-memory cache for config files
_config_cache = {}

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_config_path():
    config_path = os.path.join(ROOT_DIR, "config")
    return config_path

def _load_config_file(filename: str, key: str = None, default=None):
    """
    Loads a YAML config file and caches the result in memory.
    If key is provided, returns config[key], else returns the whole config.
    """
    cache_key = (filename, key)
    if cache_key in _config_cache:
        return _config_cache[cache_key]
    config_path = get_config_path()
    file_path = os.path.join(config_path, filename)
    with open(file_path, 'r') as config_file:
        config_data = yaml.safe_load(config_file)
    result = config_data if key is None else config_data.get(key, default)
    _config_cache[cache_key] = result
    return result

def get_data_config():
    return _load_config_file('data.yml', 'data', {})

def get_role_configs():
    return _load_config_file('roles.yml', 'roles', [])

def get_designations():
    return _load_config_file('designations.yml', 'designations', {})

def get_role_names() -> List[str]:
    roles_config = get_role_configs()
    return [role_config['role'] for role_config in roles_config]

def get_designation_names() -> List[str]:
    designations_config = get_designations()
    return list(designations_config.keys())

def get_designation_alias_map() -> Dict[str, str]:
    designations_config = get_designations()
    alias_map = {}
    for canonical, entry in designations_config.items():
        alias_map[canonical.lower()] = canonical
        for alias in entry.get("aliases", []):
            alias_map[alias.lower()] = canonical
    return alias_map

def get_unique_roles() -> List[str]:
    role_configs = get_role_configs()
    unique_roles = [entry['role'] for entry in role_configs if entry.get('is_unique', False)]
    return unique_roles

def get_crawl():
    return _load_config_file('crawl.yml')

def search_keywords(type = "local") -> Dict[str, List[str]]:
    config = _load_config_file('search.yml')
    return config.get('keywords', {})

def crawl_keywords(type = "local") -> Dict[str, List[str]]:
    config = _load_config_file('crawl.yml')
    return config.get('keywords', {})

def get_job_config(logger = None) -> JobConfig:
    config = _load_config_file('job.yml')
    if os.getenv("PIPELINE_RUN_COST_LIMIT"):
        try:
            pipeline_run_cost_limit_string = os.getenv("PIPELINE_RUN_COST_LIMIT")
            if pipeline_run_cost_limit_string:
                if logger is not None:
                    logger.info(f"Overriding pipeline_run_cost_limit with environment variable: {pipeline_run_cost_limit_string}")
                pipeline_run_cost_limit = Decimal(pipeline_run_cost_limit_string)
                config['pipeline_run_cost_limit'] = pipeline_run_cost_limit
        except (ValueError, InvalidOperation):
            pass
    return JobConfig(
        max_pages=config.get('max_pages'),
        pipeline_run_cost_limit=config.get('pipeline_run_cost_limit')
    )

def get_role_alias_map() -> Dict[str, str]:
    role_configs = get_role_configs()
    alias_map = {}
    for entry in role_configs:
        role_entry = entry['role']
        canonical_role = role_entry if isinstance(role_entry, str) else " ".join(role_entry).strip()
        if not canonical_role:
            continue
        alias_map[canonical_role.lower()] = canonical_role
        aliases = entry.get("aliases", [])
        for alias in aliases:
            alias_map[alias.lower()] = canonical_role
    return alias_map

def get_keywords() -> List[str]:
    keywords = []
    role_alias_map = get_role_alias_map()
    role_keywords = set(role_alias_map.keys()) | set(role_alias_map.values())
    designation_alias_map = get_designation_alias_map()
    designation_keywords = set(designation_alias_map.keys()) | set(designation_alias_map.values())
    crawl = crawl_keywords()
    extra_keywords = [
        "title", "email", "phone", "contact", "address",
        "start date", "elected at", "end date", "term expires",
        "current term", 
        "committee", "planning", "board", "zoning"
    ]
    keywords = list(role_keywords | designation_keywords | set(crawl) | set(extra_keywords))
    return keywords

def get_states() -> List[dict]:
    """
    Returns a list of all unique states from the configuration.
    """
    config = _load_config_file('states.yml')
    return config