"""
Environment variable loader for civicpatch.org
References variables and defaults from docker-compose.yml
"""

import os

REQUIRED_ENV_VARS = [
    # Required
    "GITHUB_APP_ID",
    "GITHUB_APP_PRIVATE_KEY_BASE64",
    "GITHUB_APP_INSTALLATION_ID",
    "CIVICPATCH_API_DB_URL",
    "INSTANCE_URL",
    "OPEN_DATA_REPO_URL",
    "MAINTAINER_EMAIL",
    "REDIS_HOST",
    "DATABASE_HASH_KEY",
    "SERVICE_API_KEY",
    "CIVICPATCH_API_DB_PASSWORD",
    "CIVICPATCH_API_DB_URL",
    "COOKIE_INSTANCE_URL",  # Only required in production, but we can just set it to .civicpatch.org in dev too for simplicity
    "SUPABASE_URL",
    "SUPABASE_SECRET_KEY",
]

OPTIONAL_ENV_VARS = [
    "APP_ENVIRONMENT",
    # Optional - needed for GitHub webhook verification
    "GITHUB_WEBHOOK_SECRET",
    # Optional - needed for the blog-sync webhook (HMAC verification)
    "BLOG_SYNC_WEBHOOK_SECRET",
    # Optional - needed for scraping
    "GOOGLE_SHEETS_SPREADSHEET_ID",
    "GOOGLE_SHEETS_PRIVATE_KEY_BASE64",
    "GOOGLE_SHEETS_CLIENT_EMAIL",
    "GOOGLE_SHEETS_TOKEN_URI",
    "STORAGE_ENDPOINT",
    "STORAGE_ACCESS_KEY_ID",
    "STORAGE_SECRET_ACCESS_KEY",
    "FRIENDLY_STORAGE_HOST",
    "TEMPORAL_HOST",
    "TEMPORAL_NAMESPACE",
    # Only needed to make edits to a jurisdiction
    "JURISDICTIONS_REPO_URL",
    "JURISDICTIONS_SYNC_APP_ID",
    "JURISDICTIONS_SYNC_APP_PRIVATE_KEY_BASE64",
    "JURISDICTIONS_SYNC_APP_INSTALLATION_ID",
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
    _optional_defaults = {
        "FRIENDLY_STORAGE_HOST": "https://cdn.civicpatch.org",
    }
    for var in OPTIONAL_ENV_VARS:
        value = os.getenv(var, _optional_defaults.get(var))
        env[var] = value
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    return env
