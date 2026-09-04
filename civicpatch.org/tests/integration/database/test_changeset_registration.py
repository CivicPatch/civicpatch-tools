"""Integration tests for registering a scrape's changeset.

Real Postgres: what these guard is `changesets_scrape_has_a_run`, a CHECK tying `kind = 'scrape'`
to a non-null `status`. The route tests mock the register functions away, so nothing else runs
this SQL — and a writer that sets the status in a second statement passes every unit test while
failing every real insert.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.changesets import (
    register_request_with_pipeline_run,
    register_request_with_pipeline_run_if_not_exists,
)
from database.database import get_pool
from shared.utils.statuses import ChangesetKind, PipelineRunStatus

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_registration/government"
_CHANGESET_ID = "d21f7c6e-4b3a-4f6d-9c11-5a0e8b7d2f34"
_ARGUMENTS = {"jurisdiction_ocdid": _OCDID, "name": "Zz city", "url": "https://zz.test"}


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
            VALUES (%s, 'zz', '{}'::jsonb, now())
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (_OCDID,),
        )
    yield
    await _wipe()


async def _stored_run():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT kind, status, progress, updated_at FROM changesets WHERE id = %s",
            (_CHANGESET_ID,),
        )
        row = await cur.fetchone()
        assert row is not None, "no changeset row was written"
        return row


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_scrape_writes_a_run():
    await register_request_with_pipeline_run(
        changeset_id=_CHANGESET_ID,
        kind=ChangesetKind.SCRAPE,
        arguments_json=_ARGUMENTS,
        jurisdiction_ocdid=_OCDID,
    )

    kind, status, progress, updated_at = await _stored_run()
    assert kind == ChangesetKind.SCRAPE.value
    assert status == PipelineRunStatus.PENDING.value
    assert progress == 0
    assert updated_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_scrape_honours_a_caller_supplied_status():
    await register_request_with_pipeline_run(
        changeset_id=_CHANGESET_ID,
        kind=ChangesetKind.SCRAPE,
        arguments_json=_ARGUMENTS,
        jurisdiction_ocdid=_OCDID,
        status=PipelineRunStatus.RUNNING,
        progress=42,
    )

    _, status, progress, _ = await _stored_run()
    assert status == PipelineRunStatus.RUNNING.value
    assert progress == 42


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_if_not_exists_writes_a_run():
    await register_request_with_pipeline_run_if_not_exists(
        changeset_id=_CHANGESET_ID,
        kind=ChangesetKind.SCRAPE,
        arguments_json=_ARGUMENTS,
        jurisdiction_ocdid=_OCDID,
    )

    kind, status, _, updated_at = await _stored_run()
    assert kind == ChangesetKind.SCRAPE.value
    assert status == PipelineRunStatus.PENDING.value
    assert updated_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_if_not_exists_leaves_a_started_run_alone():
    """The re-registration path: a worker announcing a run that already moved past PENDING."""
    await register_request_with_pipeline_run(
        changeset_id=_CHANGESET_ID,
        kind=ChangesetKind.SCRAPE,
        arguments_json=_ARGUMENTS,
        jurisdiction_ocdid=_OCDID,
        status=PipelineRunStatus.RUNNING,
        progress=42,
    )

    await register_request_with_pipeline_run_if_not_exists(
        changeset_id=_CHANGESET_ID,
        kind=ChangesetKind.SCRAPE,
        arguments_json=_ARGUMENTS,
        jurisdiction_ocdid=_OCDID,
    )

    _, status, progress, _ = await _stored_run()
    assert status == PipelineRunStatus.RUNNING.value
    assert progress == 42
