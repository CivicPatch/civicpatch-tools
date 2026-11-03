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
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
import yaml

from shared.utils.layered_config import level_config_path
from shared.schemas import JurisdictionLevel
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES

TEST_DB_URL = os.environ.get(
    "INTEGRATION_TEST_DB_URL",
    "postgres://civicpatch:test_password@127.0.0.1:6001/test_db",
)


@pytest.fixture(scope="session", autouse=True)
def no_run_is_terminal_without_finished_at():
    """A terminal run must carry `finished_at`, because that is what says the run is over.

    `expire_stale_pipeline_runs` asks `finished_at IS NULL` rather than matching a list of
    terminal names — the status column also holds step names, so it cannot. A row that breaks
    the pairing is therefore swept and rewritten to ERROR once it is six hours old, which for a
    SUCCESS row loses a publish.

    Checked once at the end of the session rather than per test: the writer is whichever fixture
    left the row, and this database survives between runs, so the damage shows up later and
    somewhere else. Two fixtures wrote the pair apart and it surfaced a day later as an
    unrelated failure in `test_a_run_stuck_on_a_step_is_expired`.
    """
    yield
    terminal = [status.value for status in TERMINAL_PIPELINE_RUN_STATUSES]
    with psycopg.connect(TEST_DB_URL) as conn:
        offenders = conn.execute(
            "SELECT id::text, status FROM pipeline_runs "
            "WHERE finished_at IS NULL AND status = ANY(%s)",
            (terminal,),
        ).fetchall()
    assert not offenders, (
        "pipeline_runs rows are terminal but unfinished, so the expiry sweep will rewrite them "
        f"to ERROR: {offenders}. Whatever wrote them set a terminal status without "
        "`finished_at` — go through `register_run`/`update_pipeline_run_status` (see "
        "tests/integration/factories.py) rather than a raw INSERT."
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


_LEVEL_ROLES = {
    level_config_path(level): yaml.safe_load((Path(__file__).parent / f"level_roles_{level}.yml").read_text())
    for level in (JurisdictionLevel.LOCAL, JurisdictionLevel.COUNTIES)
}


@pytest_asyncio.fixture(autouse=True)
async def level_configs(patch_db_url):
    """The fold reads roles from the stored config files. Written before every test, since a test
    that stores its own level file deletes it when it finishes; one that stores its own replaces it."""
    async with await psycopg.AsyncConnection.connect(TEST_DB_URL) as conn, conn.cursor() as cur:
        for path, roles in _LEVEL_ROLES.items():
            await cur.execute(
                """
                INSERT INTO jurisdiction_configs (path, content, commit_sha) VALUES (%s, %s, 'test')
                ON CONFLICT (path) DO UPDATE SET content = EXCLUDED.content
                """,
                (path, psycopg.types.json.Jsonb(roles)),
            )
        await conn.commit()
    yield
