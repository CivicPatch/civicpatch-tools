"""Pytest configuration and fixtures for api.civicpatch.org tests."""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

import os

# Add shared package to Python path for local testing
shared_path = Path(__file__).parent.parent.parent / "shared" / "src"
if shared_path.exists() and str(shared_path) not in sys.path:
    sys.path.insert(0, str(shared_path))

@pytest.fixture
def mock_redis():
    """Mock Redis store."""
    with patch('src.stores.redis_store.get') as mock_get, \
         patch('src.stores.redis_store.set') as mock_set:
        yield {'get': mock_get, 'set': mock_set}


# Fixture to clear specific environment variables before each test
@pytest.fixture(autouse=True)
def clear_test_env(monkeypatch):
    # List environment variables to override for test isolation
    vars_to_override = [
        'GITHUB_APP_ID',
        'GITHUB_APP_CLIENT_ID',
        'GITHUB_APP_CLIENT_SECRET',
        'GITHUB_APP_PRIVATE_KEY_BASE64',
        'GITHUB_APP_INSTALLATION_ID',

        'INSTANCE_URL',
        'OPEN_DATA_REPO_URL',
        'MAINTAINER_EMAIL',

        'REDIS_HOST',
        'JWT_SECRET_KEY',
        'DATABASE_HASH_KEY',
        'SERVICE_API_KEY',

        'CIVICPATCH_API_DB_PASSWORD',
        'CIVICPATCH_API_DB_URL',

        'GOOGLE_SHEETS_SPREADSHEET_ID',
        'GOOGLE_SHEETS_PRIVATE_KEY',
        'GOOGLE_SHEETS_CLIENT_EMAIL',
        'GOOGLE_SHEETS_TOKEN_URI',

        'STORAGE_ENDPOINT',
        'STORAGE_ACCESS_KEY_ID',
        'STORAGE_SECRET_ACCESS_KEY',
    ]
    for var in vars_to_override:
        monkeypatch.setenv(var, 'test-value')
    yield
