import os
import yaml
from typing import Dict, List
from decimal import Decimal, InvalidOperation
from shared.schemas import JobConfig

_data_config = None
_designations_config = None
_roles_config = None
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

def get_role_configs():
    global _roles_config
    if _roles_config is None:
        config_path = get_config_path()
        roles_config_path = os.path.join(config_path, 'roles.yml')
        with open(roles_config_path, 'r') as config_file:
            config_data = yaml.safe_load(config_file)
        _roles_config = config_data.get('roles', [])
    return _roles_config

def get_designations():
    global _designations_config
    if _designations_config is None:
        config_path = get_config_path()
        designations_file_path = os.path.join(config_path, 'designations.yml')
        with open(designations_file_path, 'r') as config_file:
            config_data = yaml.safe_load(config_file)
        _designations_config = config_data.get('designations', {})
    return _designations_config

def get_role_names() -> List[str]:
    roles_config = get_role_configs()
    return [role_config['role'] for role_config in roles_config]

def get_designation_names() -> List[str]:
    """
    Returns a list of canonical designation names from the configuration file.
    """
    designations_config = get_designations()
    return list(designations_config.keys())

def get_designation_alias_map() -> Dict[str, str]:
    """
    Build a mapping from all aliases to their canonical designation type.
    """
    designations_config = get_designations()

    alias_map = {}
    for canonical, entry in designations_config.items():
        alias_map[canonical.lower()] = canonical
        for alias in entry.get("aliases", []):
            alias_map[alias.lower()] = canonical
    return alias_map

def get_unique_roles() -> List[str]:
    """
    Returns a list of roles marked as unique for a specific government type from the configuration file.
    """
    role_configs = get_role_configs()
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

def search_keywords(type = "local") -> Dict[str, List[str]]:
    config_path = get_config_path()
    search_config_path = os.path.join(config_path, 'search.yml')
    with open(search_config_path, 'r') as config_file:
        config = yaml.safe_load(config_file)
    
    return config.get('keywords', {})

def crawl_keywords(type = "local") -> Dict[str, List[str]]:
    config_path = get_config_path()
    crawl_config_path = os.path.join(config_path, 'crawl.yml')
    with open(crawl_config_path, 'r') as config_file:
        config = yaml.safe_load(config_file)
    
    return config.get('keywords', {})

def get_job_config(logger = None) -> JobConfig:
    # You can override certain properties
    global _job_config
    if _job_config is None:
        config_path = get_config_path()
        process_file_path = os.path.join(config_path, 'job.yml')
        with open(process_file_path, 'r') as config_file:
            _job_config = yaml.safe_load(config_file)

    if os.getenv("PIPELINE_RUN_COST_LIMIT"):
        try:
            pipeline_run_cost_limit_string = os.getenv("PIPELINE_RUN_COST_LIMIT")
            if pipeline_run_cost_limit_string:
                if logger is not None:
                    logger.info(f"Overriding pipeline_run_cost_limit with environment variable: {pipeline_run_cost_limit_string}")
                pipeline_run_cost_limit = Decimal(pipeline_run_cost_limit_string)
                _job_config['pipeline_run_cost_limit'] = pipeline_run_cost_limit
        except (ValueError, InvalidOperation):
            pass
    return JobConfig(
        max_pages=_job_config.get('max_pages'),
        pipeline_run_cost_limit=_job_config.get('pipeline_run_cost_limit')
    )

def get_role_alias_map() -> Dict[str, str]:
    role_configs = get_role_configs()
    alias_map = {}

    for entry in role_configs:
        role_entry = entry['role']
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

def get_keywords() -> List[str]:
    """
    Combines all search keywords (including roles and designations and their aliases)
    into a single deduplicated list.
    """
    keywords = []

    # Get all role keywords (canonical + aliases)
    role_alias_map = get_role_alias_map()
    role_keywords = set(role_alias_map.keys()) | set(role_alias_map.values())

    # Get all designation keywords (canonical + aliases)
    designation_alias_map = get_designation_alias_map()
    designation_keywords = set(designation_alias_map.keys()) | set(designation_alias_map.values())

    # Crawl keywords (flatten if dict)
    crawl = crawl_keywords()

    # Extra keywords for content filtering
    extra_keywords = [
        "title", "email", "phone", "contact", "address",
        "start date", "elected at", "end date", "term expires",
        "current term"
    ]

    # Combine and dedupe all
    keywords = list(role_keywords | designation_keywords | set(crawl) | set(extra_keywords))

    return keywords