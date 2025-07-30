import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def get_data_source_path():
    """
    Returns the absolute path to the 'data_source' directory.
    """
    data_source_path = os.path.join(ROOT_DIR, "data_source")

    if not os.path.exists(data_source_path):
        raise FileNotFoundError(f"'data_source' directory not found at {data_source_path}")

    return data_source_path

def get_municipalities_file_path(state):
    """
    Returns the file path for the municipalities JSON file based on the state.
    """

    data_source_dir = get_data_source_path()
    
    return os.path.join(data_source_dir, state, 'municipalities.json')