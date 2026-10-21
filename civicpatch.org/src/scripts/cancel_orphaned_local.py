"""Cancel the people_collector runs a pipelines-server reload orphaned on dev: their Temporal
workflow, then their row, as the cancel endpoint does. The reload kills the scrape mid-step, so
the row stays unfinished and the jurisdiction cannot be scraped again until this runs. Dev only.

    mise run cancel-orphaned -- <jurisdiction ocdid>...
"""

import asyncio
import sys

import lib.temporal.client as temporal_service
from database.database import close_pool, get_pool
from database.pipeline_runs import update_pipeline_run_status
from shared.utils.statuses import PipelineRunKind, PipelineRunStatus


async def unfinished_runs(jurisdiction_ocdids: list[str]) -> list[tuple[str, str]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, jurisdiction_ocdid FROM pipeline_runs"
            " WHERE finished_at IS NULL AND kind = %s AND jurisdiction_ocdid = ANY(%s)",
            (PipelineRunKind.PEOPLE_COLLECTOR, jurisdiction_ocdids),
        )
        return await cur.fetchall()


async def main(jurisdiction_ocdids: list[str]) -> None:
    try:
        for run_id, jurisdiction_ocdid in await unfinished_runs(jurisdiction_ocdids):
            await temporal_service.cancel_workflow(jurisdiction_ocdid)
            applied = await update_pipeline_run_status(run_id, status=PipelineRunStatus.CANCELLED)
            print(f"{'cancelled' if applied else 'skipped  '} {run_id} {jurisdiction_ocdid}", flush=True)
    finally:
        await close_pool()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1:]))
