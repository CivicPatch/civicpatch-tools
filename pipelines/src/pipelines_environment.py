"""
Environment variable loader for civicpatch.org
References variables and defaults from docker-compose.yml
"""
import os

REQUIRED_ENV_VARS = [
    "CIVICPATCH_ORG_URL",
    "SERVICE_API_KEY",
    "OPEN_DATA_REPO_URL",
]

OPTIONAL_ENV_VARS = [
    "APP_ENVIRONMENT",
    "API_URL",
    "LOG_LEVEL",

    "GOOGLE_GEMINI_TOKEN",
    "OPEN_ROUTER_TOKEN",
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
