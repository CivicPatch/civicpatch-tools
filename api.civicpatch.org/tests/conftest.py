"""Pytest configuration and fixtures for api.civicpatch.org tests."""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

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
