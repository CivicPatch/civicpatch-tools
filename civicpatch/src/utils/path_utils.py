import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_config_path():
    """
    Returns the absolute path to the configuration file.
    """
    config_path = os.path.join(ROOT_DIR, "config")

    return config_path

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
        raise FileNotFoundError(f"'data_source' directory not found at {data_source_path}")

    return data_source_path

