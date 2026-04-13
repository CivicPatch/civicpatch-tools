from temporalio import activity

import core.pull_request_sync as pr_sync
import core.open_data_sync as data_sync


@activity.defn
async def sync_pr_state_activity() -> None:
    await pr_sync.sync_open_pr_state()


@activity.defn
async def od_sync_activity() -> None:
    await data_sync.od_sync()
