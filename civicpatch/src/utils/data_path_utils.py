import os
import utils.data_utils
import utils.path_utils

def get_pipeline_context_file_path(state, geoid):
    """
    Returns the absolute path to the pipeline file.
    """
    municipality_folder_name = utils.data_utils.get_municipality_folder_name(state, geoid)
    data_source_path = utils.path_utils.get_data_source_path()
    pipeline_file_path = os.path.join(data_source_path, state, "municipalities", municipality_folder_name, 'pipeline_context.json')

    return pipeline_file_path

def get_cache_path(state, geoid):
    """
    Returns the absolute path to the cache directory for a given state and GEOID.
    """
    municipality_folder_name = utils.data_utils.get_municipality_folder_name(state, geoid)
    data_source_path = utils.path_utils.get_data_source_path()
    cache_path = os.path.join(data_source_path, state, "municipalities", municipality_folder_name, 'cache')

    if not os.path.exists(cache_path):
        os.makedirs(cache_path)

    return cache_path

def get_people_path(state, geoid):
    """
    Returns the absolute path to the people directory for a given state and GEOID.
    """
    municipality_folder_name = utils.data_utils.get_municipality_folder_name(state, geoid)
    data_source_path = utils.path_utils.get_data_source_path()
    people_path = os.path.join(data_source_path, state, "municipalities", municipality_folder_name, 'people')

    if not os.path.exists(people_path):
        os.makedirs(people_path)

    return people_path

def get_images_path(state, geoid):
    """
    Returns the absolute path to the images directory for a given state and GEOID.
    """
    municipality_folder_name = utils.data_utils.get_municipality_folder_name(state, geoid)
    data_source_path = utils.path_utils.get_data_source_path()
    images_path = os.path.join(data_source_path, state, "municipalities", municipality_folder_name, 'images')

    if not os.path.exists(images_path):
        os.makedirs(images_path)

    return images_path

def get_municipality_path(state, geoid):
    municipality_name = utils.data_utils.get_municipality_folder_name(state, geoid)
    return os.path.join(state, "municipalities", municipality_name)

def get_data_municipality_path(state, geoid):
    """
    Returns the absolute path to the municipalities directory for a given state and GEOID.
    """
    data_path = utils.path_utils.get_data_path()
    municipality_path = get_municipality_path(state, geoid)
    return os.path.join(data_path, municipality_path)

def get_data_source_municipality_path(state, geoid):
    """
    Returns the absolute path to the municipalities directory for a given state and GEOID.
    """
    data_source_path = utils.path_utils.get_data_source_path()
    municipality_path = get_municipality_path(state, geoid)
    return os.path.join(data_source_path, municipality_path)
