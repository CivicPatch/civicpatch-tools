from temporalio import activity

import services.pull_request_sync as pr_sync
import services.open_data_sync as data_sync
import services.pull_request_merge as pull_request_merge
import database.pipeline_runs as pipeline_runs_db
import database.review_session_entries as review_session_entries_db
from lib.temporal.types import MergeRequest
from shared.utils.timeouts import PEOPLE_COLLECTOR_EXECUTION_TIMEOUT


@activity.defn
async def sync_pr_state_activity() -> None:
    await pr_sync.sync_open_pr_state()


@activity.defn
async def od_sync_activity() -> None:
    await data_sync.sync_all()


@activity.defn
async def expire_stale_pipeline_runs_activity() -> None:
    expired = await pipeline_runs_db.expire_stale_pipeline_runs(PEOPLE_COLLECTOR_EXECUTION_TIMEOUT)
    if expired:
        activity.logger.warning("Expired %d stale pipeline run(s): %s", len(expired), expired)


@activity.defn
async def cleanup_stale_review_entries_activity() -> None:
    result = await review_session_entries_db.purge_stale_idle_sessions()
    if result["entries_deleted"]:
        activity.logger.info(
            "Review session cleanup: %d entries deleted",
            result["entries_deleted"],
        )


@activity.defn
async def merge_pr_activity(request: MergeRequest) -> None:
    await pull_request_merge.do_merge(
        pull_request_number=request.pull_request_number,
        request_id=request.request_id,
        approved_by=request.approved_by,
        user_id=request.user_id,
        merge_key=request.merge_key,
    )
