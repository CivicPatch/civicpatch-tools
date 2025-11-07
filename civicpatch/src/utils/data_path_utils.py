import os
from typing import Any, List

import yaml

from utils import id_utils

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_data_path():
    """
    Returns the absolute path to the 'data' directory.
    """
    data_path = os.path.join(ROOT_DIR, "data")

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"'data' directory not found at {data_path}")

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


def get_pipeline_context_file_path(jurisdiction_id: str):
    """
    Returns the absolute path to the pipeline file.
    """
    data_source_path = get_data_source_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    pipeline_file_path = os.path.join(
        data_source_path, folder_path, "pipeline_context.json"
    )

    return pipeline_file_path


def get_config_file_path(jurisdiction_id: str):
    data_source_path = get_data_source_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    config_file_path = os.path.join(data_source_path, folder_path, "config.yml")

    return config_file_path


# Need a better name for this...
# File names will always end in place__<place_name>.yml
# It used to end in people.yml
def get_people_file_path(jurisdiction_id):
    data_path = get_data_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)

    people_file_path = os.path.join(data_path, f"{folder_path}.yml")

    return people_file_path


# Serialized
def get_people(jurisdiction_id: str) -> List[Any]:
    people_file_path = get_people_file_path(jurisdiction_id)

    if not os.path.exists(people_file_path):
        return {}

    with open(people_file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
        return data or {}


def update_people_for_jurisdiction(
    file_path: str, jurisdiction_id: str, people: List[Any]
):
    # Ensure the directory exists
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # Remove any existing entries with the same jurisdiction_id
    with open(file_path, "w+") as file:
        data = yaml.safe_load(file) or []
        data[:] = [p for p in data if p[jurisdiction_id] != jurisdiction_id]
        data.extend(people)
        file.write(yaml.dump(data, sort_keys=False, allow_unicode=True))


# Serialized, filtered by jurisdiction type
def get_people_from_jurisdiction_type(jurisdiction_id: str) -> List[Any]:
    people_file_path = get_people_file_path(jurisdiction_id)

    if not os.path.exists(people_file_path):
        return []

    with open(people_file_path, "r") as file:
        data = yaml.safe_load(file)

    print("data is now", data)
    data_from_jurisdiction_type = [
        p for p in data if p.get("jurisdiction_id") == jurisdiction_id
    ]
    return data_from_jurisdiction_type


def get_cache_path(jurisdiction_id: str):
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    data_source_path = get_data_source_path()
    cache_path = os.path.join(data_source_path, folder_path, "cache")

    if not os.path.exists(cache_path):
        os.makedirs(cache_path)

    return cache_path


def get_images_path(jurisdiction_id):
    data_source_path = get_data_source_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    images_path = os.path.join(data_source_path, folder_path, "images")
    if not os.path.exists(images_path):
        os.makedirs(images_path)

    return images_path


def get_data_municipality_path(jurisdiction_id: str):
    data_path = get_data_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    return os.path.join(data_path, folder_path)


def get_data_source_municipality_path(jurisdiction_id: str):
    data_source_path = get_data_source_path()
    folder_path = id_utils.jurisdiction_id_to_folder(jurisdiction_id)
    return os.path.join(data_source_path, folder_path)
