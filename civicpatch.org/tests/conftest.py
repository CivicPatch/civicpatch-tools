"""Pytest configuration and fixtures for civicpatch.org tests."""
import sys
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Add shared package to Python path for local testing
shared_path = Path(__file__).parent.parent.parent / "shared" / "src"
if shared_path.exists() and str(shared_path) not in sys.path:
    sys.path.insert(0, str(shared_path))

# Set env vars before any module imports so module-level get_env_vars() calls succeed
import src.environment
_test_env = {var: f"test-{var.lower()}" for var in src.environment.REQUIRED_ENV_VARS + src.environment.OPTIONAL_ENV_VARS}
for _var, _val in _test_env.items():
    os.environ.setdefault(_var, _val)


@pytest.fixture(autouse=True)
def patch_get_env_vars(monkeypatch):
    test_env = {var: f"test-{var.lower()}" for var in src.environment.REQUIRED_ENV_VARS + src.environment.OPTIONAL_ENV_VARS}
    monkeypatch.setattr("src.environment.get_env_vars", lambda: test_env)
    yield



@pytest.fixture
def mock_redis():
    """Mock Redis store."""
    with patch('src.stores.redis_store.get') as mock_get, \
         patch('src.stores.redis_store.set') as mock_set:
        yield {'get': mock_get, 'set': mock_set}
