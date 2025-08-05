import os
import yaml
import utils.path_utils as path_utils

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

def get_search():
    """
    Returns the search configuration from the configuration file.
    """
    config_path = path_utils.get_config_path()
    search_file_path = os.path.join(config_path, 'search.yaml')
    with open(search_file_path, 'r') as config_file:
        search_config = yaml.safe_load(config_file)
    
    return search_config