"""A sheet import landing in the review queue, as an activity row.

Real Postgres: the write happens on its own connection, best-effort, after the changeset
insert commits — a mocked connection cannot honestly exercise that ordering.

Isolation: sentinel state 'zq', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio

import database.changeset_batches as batches_db
from database.changesets import register_sheet_import_changeset
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from shared.utils.statuses import ActivityType

_OCDID = "ocd-jurisdiction/country:us/state:zq/place:zq_activity/government"
_BATCH_LOCK_KEY = "zq_sheet_import_activity"


async def _activity_rows(ocdid: str) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type, changeset_id::text FROM activity "
            "WHERE jurisdiction_ocdid = %s ORDER BY created_at",
            (ocdid,),
        )
        return [{"type": row[0], "changeset_id": row[1]} for row in await cur.fetchall()]


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute(
            "DELETE FROM changeset_batches WHERE lock_key = %s", (_BATCH_LOCK_KEY,)
        )
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zq', 'local')",
            (_OCDID,),
        )
        await conn.commit()
    yield
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_importing_a_jurisdiction_logs_a_sheet_import():
    batch_id = await batches_db.start(
        batches_db.BatchKind.SHEET_IMPORT, _BATCH_LOCK_KEY, SYSTEM_USER_ID, {}
    )
    changeset_id = str(uuid.uuid4())

    await register_sheet_import_changeset(changeset_id, _OCDID, SYSTEM_USER_ID, batch_id)

    rows = await _activity_rows(_OCDID)
    assert rows == [{"type": ActivityType.SHEET_IMPORT.value, "changeset_id": changeset_id}]
