from temporalio import activity

import core.pull_request_sync as pr_sync
import core.open_data_sync as data_sync
import database.pipeline_runs as pipeline_runs_db
from shared.utils.timeouts import PEOPLE_COLLECTOR_EXECUTION_TIMEOUT


@activity.defn
async def sync_pr_state_activity() -> None:
    await pr_sync.sync_open_pr_state()


@activity.defn
async def od_sync_activity() -> None:
    await data_sync.od_sync()


@activity.defn
async def expire_stale_pipeline_runs_activity() -> None:
    expired = await pipeline_runs_db.expire_stale_pipeline_runs(PEOPLE_COLLECTOR_EXECUTION_TIMEOUT)
    if expired:
        activity.logger.warning("Expired %d stale pipeline run(s): %s", len(expired), expired)
