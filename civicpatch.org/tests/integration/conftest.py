"""
Fixtures for integration tests that connect to the integration test database.

Start the test DB before running:
  mise run tcp-db-up && mise run tcp-db-migrate

Or run everything in one shot:
  mise run tcp-integration

Override the URL for CI by setting INTEGRATION_TEST_DB_URL. We use a separate
env var (not CIVICPATCH_API_DB_URL) because the root conftest poisons that name
via os.environ.setdefault before this module loads.
"""
import os
import pytest_asyncio

TEST_DB_URL = os.environ.get(
    "INTEGRATION_TEST_DB_URL",
    "postgres://civicpatch:test_password@127.0.0.1:6001/test_db",
)


@pytest_asyncio.fixture(autouse=True)
async def patch_db_url(monkeypatch):
    """Point the connection pool at the dev DB for every integration test."""
    import database.database as db_module
    # Close any pool opened by previous tests so the URL change takes effect.
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None
    # Patch the get_env_vars reference in database.database directly — the root
    # conftest patches src.environment.get_env_vars which is a different reference.
    original_get_env_vars = db_module.get_env_vars
    monkeypatch.setattr(db_module, "get_env_vars", lambda: {**original_get_env_vars(), "CIVICPATCH_API_DB_URL": TEST_DB_URL})
    yield
    # Tear down the pool after each test so tests are isolated.
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None
