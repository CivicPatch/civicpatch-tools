"""Integration tests for synced_files (sync-cursor) DB ops.

Exercised against real Postgres because these functions are pure SQL at the DB
boundary — the honest layer (mocking a cursor would only re-assert the SQL string).

Run with: mise run tcp-integration

Isolation: tests use a sentinel path prefix that can't collide with real synced
files, and clean_synced_files wipes those rows before/after each test.
"""
import pytest
import pytest_asyncio

from database.database import get_pool
from database.synced_files import (
    delete_synced_files,
    get_synced_file_shas,
    upsert_synced_file,
)

_SENTINEL_PREFIX = "test-synced-files/"


async def _wipe_sentinel_files():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM synced_files WHERE path LIKE %s",
            (_SENTINEL_PREFIX + "%",),
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_synced_files():
    await _wipe_sentinel_files()
    yield
    await _wipe_sentinel_files()


async def _read_synced_at(path: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT synced_at FROM synced_files WHERE path = %s", (path,))
        row = await cur.fetchone()
        return row[0] if row else None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upsert_inserts_then_get_returns_sha():
    path = _SENTINEL_PREFIX + "a.yml"
    await upsert_synced_file(path, "sha-aaa")
    shas = await get_synced_file_shas()
    assert shas[path] == "sha-aaa"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upsert_on_conflict_updates_sha_and_bumps_synced_at():
    path = _SENTINEL_PREFIX + "b.yml"
    await upsert_synced_file(path, "sha-old")
    first = await _read_synced_at(path)

    await upsert_synced_file(path, "sha-new")
    shas = await get_synced_file_shas()
    assert shas[path] == "sha-new"

    second = await _read_synced_at(path)
    assert first is not None and second is not None
    assert second >= first  # synced_at advanced (>= guards clock resolution)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_removes_only_named_paths():
    keep = _SENTINEL_PREFIX + "keep.yml"
    drop = _SENTINEL_PREFIX + "drop.yml"
    await upsert_synced_file(keep, "k")
    await upsert_synced_file(drop, "d")

    await delete_synced_files([drop])

    shas = await get_synced_file_shas()
    assert drop not in shas
    assert shas[keep] == "k"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_empty_list_is_noop():
    await delete_synced_files([])  # must not raise
