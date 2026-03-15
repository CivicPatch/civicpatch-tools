"""
Environment variable loader for api.civicpatch.org
References variables and defaults from docker-compose.yml
"""
import os

REQUIRED_ENV_VARS = [
    # Required
    "GITHUB_APP_ID",
    "GITHUB_APP_CLIENT_ID",
    "GITHUB_APP_CLIENT_SECRET",
    "GITHUB_APP_PRIVATE_KEY_BASE64",
    "GITHUB_APP_INSTALLATION_ID",
    "CIVICPATCH_API_DB_URL",
    "INSTANCE_URL",
    "OPEN_DATA_REPO_URL",
    "MAINTAINER_EMAIL",
    "REDIS_HOST",
    "JWT_SECRET_KEY",
    "DATABASE_HASH_KEY",
    "SERVICE_API_KEY",
    "CIVICPATCH_API_DB_PASSWORD",
    "CIVICPATCH_API_DB_URL",
]

OPTIONAL_ENV_VARS = [
    # Optional - needed for scraping
    "GOOGLE_SHEETS_SPREADSHEET_ID",
    "GOOGLE_SHEETS_PRIVATE_KEY",
    "GOOGLE_SHEETS_CLIENT_EMAIL",
    "GOOGLE_SHEETS_TOKEN_URI",
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
