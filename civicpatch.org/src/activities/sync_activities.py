from temporalio import activity

import services.github.pull_request_sync_service as pr_sync
import services.github.data_sync_service as data_sync


@activity.defn
async def sync_pr_state_activity() -> None:
    await pr_sync.sync_open_pr_state()


@activity.defn
async def od_sync_activity() -> None:
    await data_sync.od_sync()
