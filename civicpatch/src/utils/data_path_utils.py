import os
import yaml
from typing import Any, List, Dict
from schemas import Person
import utils.path_utils
from utils import id_utils

def get_pipeline_context_file_path(jurisdiction_id: str):
    """
    Returns the absolute path to the pipeline file.
    """
    data_source_path = utils.path_utils.get_data_source_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    pipeline_file_path = os.path.join(data_source_path,folder_path, 'pipeline_context.json')

    return pipeline_file_path

# Need a better name for this...
# File names will always end in place__<place_name>.yml
# It used to end in people.yml
def get_people_file_path(jurisdiction_id):
    data_path = utils.path_utils.get_data_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)

    people_file_path = os.path.join(data_path, f"{folder_path}.yml")

    return people_file_path

# Serialized
def get_people(jurisdiction_id: str) -> Dict[str, Any]:
    people_file_path = get_people_file_path(jurisdiction_id)
    
    if not os.path.exists(people_file_path):
        return {}

    with open(people_file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
        return data

# Serialized, filtered by jurisdiction type
def get_people_from_jurisdiction_type(jurisdiction_id: str) -> List[Any]:
    people_file_path = get_people_file_path(jurisdiction_id)
    jurisdiction_type = id_utils.parse_jurisdiction_id(jurisdiction_id).jurisdiction_type

    if not os.path.exists(people_file_path):
        return []

    with open(people_file_path, "r") as file:
        data = yaml.safe_load(file)
        data_from_jurisdiction_type = data.get(jurisdiction_type, []) 
        return data_from_jurisdiction_type

def get_cache_path(jurisdiction_id: str):
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    data_source_path = utils.path_utils.get_data_source_path()
    cache_path = os.path.join(data_source_path, folder_path, 'cache')

    if not os.path.exists(cache_path):
        os.makedirs(cache_path)

    return cache_path

def get_images_path(jurisdiction_id):
    data_source_path = utils.path_utils.get_data_source_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    images_path = os.path.join(data_source_path, folder_path, 'images')
    if not os.path.exists(images_path):
        os.makedirs(images_path)

    return images_path

def get_data_municipality_path(jurisdiction_id: str):
    data_path = utils.path_utils.get_data_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    return os.path.join(data_path, folder_path)

def get_data_source_municipality_path(jurisdiction_id: str):
    data_source_path = utils.path_utils.get_data_source_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    return os.path.join(data_source_path, folder_path)