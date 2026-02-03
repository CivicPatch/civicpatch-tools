import os
from typing import Any, List

import yaml

from shared.utils import id_utils

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def get_data_path():
    """
    Returns the absolute path to the 'data' directory.
    """
    data_path = os.path.join(ROOT_DIR, "data")

    return data_path


def get_data_source_path():
    """
    Returns the absolute path to the 'data_source' directory.
    """
    data_source_path = os.path.join(ROOT_DIR, "data_source")

    if not os.path.exists(data_source_path):
        raise FileNotFoundError(
            f"'data_source' directory not found at {data_source_path}"
        )

    return data_source_path

def get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid: str):
    data_source_path = get_data_source_path()
    folder_path = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return os.path.join(data_source_path, folder_path)

def get_workflow_context_file_path(jurisdiction_ocdid: str):
    """
    Returns the absolute path to the pipeline file.
    """
    jurisdiction_ocdid_path = get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    return os.path.join(
        jurisdiction_ocdid_path, "workflow_context.json"
    )

def get_config_file_path(jurisdiction_ocdid: str):
    data_source_path = get_data_source_path()
    folder_path = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    config_file_path = os.path.join(data_source_path, folder_path, "config.yml")

    return config_file_path

def get_metadata_file_path(jurisdiction_ocdid: str):
    data_source_path = get_data_source_path()
    folder_path = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    metadata_file_path = os.path.join(data_source_path, folder_path, "metadata.yml")

    return metadata_file_path

def get_data_file_path(jurisdiction_ocdid):
    data_path = get_data_path()
    folder_path = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)

    data_file_path = os.path.join(data_path, f"{folder_path}.yml")

    return data_file_path 


# Serialized
def get_data(jurisdiction_ocdid: str) -> List[Any]:
    data_file_path = get_data_file_path(jurisdiction_ocdid)

    if not os.path.exists(data_file_path):
        return []

    with open(data_file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
        return data or []


def update_data_for_jurisdiction(
    jurisdiction_ocdid: str, serialized_data: List[Any]
):
    data_file_path = get_data_file_path(jurisdiction_ocdid)
    if not os.path.exists(os.path.dirname(data_file_path)):
        os.makedirs(os.path.dirname(data_file_path))

    with open(data_file_path, "w+") as file:
        file.write(yaml.dump(serialized_data, sort_keys=False, allow_unicode=True))

def get_cache_path(jurisdiction_ocdid: str):
    folder_path = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    data_source_path = get_data_source_path()
    cache_path = os.path.join(data_source_path, folder_path, "cache")

    if not os.path.exists(cache_path):
        os.makedirs(cache_path)

    return cache_path


def get_images_path(jurisdiction_ocdid):
    data_source_path = get_data_source_path()
    folder_path = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    images_path = os.path.join(data_source_path, folder_path, "images")
    if not os.path.exists(images_path):
        os.makedirs(images_path)

    return images_path

