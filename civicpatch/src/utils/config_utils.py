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