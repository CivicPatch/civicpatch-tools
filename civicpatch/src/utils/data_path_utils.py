import os
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

def get_people_file_path(jurisdiction_id):
    data_path = utils.path_utils.get_data_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)

    people_file_path = os.path.join(data_path, folder_path, "people.yml")

    return people_file_path

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