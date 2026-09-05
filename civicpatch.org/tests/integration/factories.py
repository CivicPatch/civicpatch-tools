"""Row builders for integration tests, driven through the writers production actually uses.

Runs are why this module exists. A run starts with **no changeset**: `register_run` has no
`changeset_id` parameter at all, and one is minted only at ingest, only on success, by
`register_scrape_changeset`. Tests that hand-rolled
`INSERT INTO pipeline_runs (..., changeset_id)` described a row only migration 169's backfill
ever produced, so readers that broke on real in-flight runs stayed green — see
`test_a_run_in_flight_has_no_changeset_yet`.

Going through the real writers is the point: a fixture that restates the schema is a second,
unenforced claim about it, and it drifts the moment the writer changes.

Backdating is the one thing done in raw SQL. Windows are a test concern; production never moves
a row through time.
"""

import uuid

from database.changesets import register_scrape_changeset
from database.database import get_pool
from database.pipeline_runs import register_run, update_pipeline_run_status
from shared.utils.statuses import PipelineRunStatus


async def seed_jurisdiction(jurisdiction_ocdid: str, state: str, name: str = "Zy Place") -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
            VALUES (%s, %s, %s::jsonb, now())
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (jurisdiction_ocdid, state, f'{{"name": "{name}"}}'),
        )
        await conn.commit()


async def start_run(
    jurisdiction_ocdid: str,
    *,
    status: PipelineRunStatus = PipelineRunStatus.INIT,
    progress: int = 0,
    created_by_user_id: str | None = None,
) -> str:
    """An attempt in flight: no changeset, no `finished_at`, exactly as production starts one."""
    run_id = str(uuid.uuid4())
    await register_run(
        run_id, jurisdiction_ocdid, {}, created_by_user_id, status, progress
    )
    return run_id


async def fail_run(run_id: str) -> None:
    """A run that died. It reaches no ingest, so it mints no changeset and is in no proposal count."""
    await update_pipeline_run_status(run_id, PipelineRunStatus.ERROR.value)


async def complete_run(run_id: str) -> str:
    """A run that reached ingest: mint the proposal, link it, then report the terminal status."""
    changeset_id = await register_scrape_changeset(run_id)
    await update_pipeline_run_status(run_id, PipelineRunStatus.SUCCESS.value)
    return changeset_id


async def backdate_run(run_id: str, days: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE pipeline_runs
            SET created_at = now() - make_interval(days => %s),
                updated_at = now() - make_interval(days => %s)
            WHERE id = %s
            """,
            (days, days, run_id),
        )
        await conn.commit()


async def backdate_changeset(changeset_id: str, days: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE changesets
            SET created_at = now() - make_interval(days => %s),
                updated_at = now() - make_interval(days => %s)
            WHERE id::text = %s
            """,
            (days, days, changeset_id),
        )
        await conn.commit()
