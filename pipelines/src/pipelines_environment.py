"""
Environment variable loader for civicpatch.org
References variables and defaults from docker-compose.yml
"""
import os

REQUIRED_ENV_VARS = [
    "CIVICPATCH_ORG_URL",
    "SERVICE_API_KEY"
]

OPTIONAL_ENV_VARS = [
    "API_URL",
    "PIPELINE_RUN_COST_LIMIT",
    "LOG_LEVEL",

    "GOOGLE_SEARCH_TOKEN",
    "GOOGLE_SEARCH_ENGINE_ID",

    "GOOGLE_GEMINI_TOKEN",
    "OPEN_ROUTER_TOKEN",
    "JOB_RUN_URL",
    "STORAGE_ENDPOINT",
    "STORAGE_ACCESS_KEY_ID",
    "STORAGE_SECRET_ACCESS_KEY",
]

def get_env_vars():
    """
    Returns a dictionary of all required and optional environment variables.
    Raises ValueError if any required variable is missing.
    """
    env = {}
    missing = []
    # Always grab all environment variables
    for var in REQUIRED_ENV_VARS:
        value = os.getenv(var)
        if value is None:
            missing.append(var)
        env[var] = value
    for var in OPTIONAL_ENV_VARS:
        value = os.getenv(var)
        env[var] = value
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    return env
