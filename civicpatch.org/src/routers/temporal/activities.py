from temporalio import activity

import core.pull_request_sync as pr_sync
import core.open_data_sync as data_sync
import database.pipeline_runs as pipeline_runs_db
import database.review_session_navigation as review_session_nav_db
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


@activity.defn
async def cleanup_stale_review_entries_activity() -> None:
    result = await review_session_nav_db.cleanup_stale_review_session_entries()
    if result["entries_deleted"]:
        activity.logger.info(
            "Review session cleanup: %d entries deleted",
            result["entries_deleted"],
        )
