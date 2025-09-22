import os
import yaml
import utils.path_utils as path_utils
from typing import Dict, List

def get_divisions():
    """
    Returns a list of divisions from the configuration file.
    """
    config_path = path_utils.get_config_path()
    divisions_file_path = os.path.join(config_path, 'divisions.yaml')
    with open(divisions_file_path, 'r') as config_file:
        config_data = yaml.safe_load(config_file)
    
    return config_data.get('divisions', [])

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
    """
    Returns a dictionary of government types from the configuration file.
    """
    config_path = path_utils.get_config_path()
    government_types_file_path = os.path.join(config_path, 'government_types.yaml')
    with open(government_types_file_path, 'r') as config_file:
        config_data = yaml.safe_load(config_file)
    
    return config_data.get('government_types', {})

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
    
    Args:
        government_type: The type of government (e.g., "mayor_council", "commission").
    
    Returns:
        List of role configurations associated with the specified government type.
    """
    government_types = get_government_types()
    return government_types.get(government_type, {}).get('roles', [])

def get_crawl():
    """
    Returns the crawl configuration from the configuration file.
    """
    config_path = path_utils.get_config_path()
    crawl_file_path = os.path.join(config_path, 'crawl.yaml')
    with open(crawl_file_path, 'r') as config_file:
        crawl_config = yaml.safe_load(config_file)
    
    return crawl_config

def search_keywords(government_type: str) -> Dict[str, List[str]]:
    """
    Returns the search keywords from the configuration file.
    """
    config_path = path_utils.get_config_path()
    government_types_file_path = os.path.join(config_path, 'government_types.yaml')
    with open(government_types_file_path, 'r') as config_file:
        config = yaml.safe_load(config_file)
        government_types_config = config.get('government_types', {})

    government_type_config = government_types_config.get(government_type, {})
    return government_type_config.get('keywords', [])

def get_process():
    """
    Returns the process configuration from the configuration file.
    """
    config_path = path_utils.get_config_path()
    process_file_path = os.path.join(config_path, 'process.yaml')
    with open(process_file_path, 'r') as config_file:
        process_config = yaml.safe_load(config_file)
    
    return process_config

def get_role_alias_map(government_type: str) -> Dict[str, str]:
    role_configs = get_role_configs_by_government_type(government_type)
    alias_map = {}
    for entry in role_configs:
        canonical = entry["role"]
        alias_map[canonical.lower()] = canonical
        for alias in entry.get("aliases", []):
            alias_map[alias.lower()] = canonical
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
                      "start date", "elected at", "end date", "term expires"]
    keywords.update(extra_keywords)

    return list(keywords)