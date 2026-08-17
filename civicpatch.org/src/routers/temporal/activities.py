from temporalio import activity

import services.pull_request_sync as pr_sync
import services.jurisdiction_edit_reconcile as edit_reconcile
import services.open_data_sync as data_sync
import services.pull_request_merge as pull_request_merge
import services.publish as publish_service
import database.pipeline_runs as pipeline_runs_db
import database.review_session_entries as review_session_entries_db
from database.issues import upsert_issue
from lib.temporal.types import MergeRequest, OpenDataCommitRequest
from shared.utils.statuses import PipelineIssueType
from shared.utils.timeouts import PEOPLE_COLLECTOR_EXECUTION_TIMEOUT

# A run that dies before send_error uploads is expired to ERROR with no issue of its own.
# Raise the same generic-failure issue the collector raises (PIPELINE_ERROR), so the
# jurisdiction lands in `blocked` (excluded by get_pending_issue_ocdids) instead of
# silently re-queuing forever.
_STALE_RUN_ISSUE_DETAIL = {"error": "pipeline run timed out and was expired"}


@activity.defn
async def sync_pr_state_activity() -> None:
    await pr_sync.sync_open_pr_state()


@activity.defn
async def od_sync_activity() -> None:
    await data_sync.sync_all()
    # After the projection, not inside it: any pending edit whose value is now live
    # is done, however it got there. Follows the jurisdiction projection if that ever
    # moves to its own workflow.
    await edit_reconcile.reconcile_landed_jurisdiction_edits()


@activity.defn
async def od_sync_targeted_activity(jurisdiction_ocdids: list[str]) -> None:
    await data_sync.sync_by_ocdids(jurisdiction_ocdids)


@activity.defn
async def expire_stale_pipeline_runs_activity() -> None:
    expired = await pipeline_runs_db.expire_stale_pipeline_runs(PEOPLE_COLLECTOR_EXECUTION_TIMEOUT)
    if not expired:
        return
    activity.logger.warning("Expired %d stale pipeline run(s): %s", len(expired), expired)
    for request_id in expired:
        await upsert_issue(request_id, PipelineIssueType.PIPELINE_ERROR, [_STALE_RUN_ISSUE_DETAIL])


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


@activity.defn
async def commit_open_data_activity(request: OpenDataCommitRequest) -> None:
    """Render this request's file from the database and write it to open-data.

    Raises on failure so Temporal retries. Safe to run repeatedly: the content comes from the
    database, not from the workflow's arguments, so a second attempt writes whatever is true
    now rather than replaying a stale render.
    """
    written = await publish_service.commit_rendered_file(
        file_path=request.file_path,
        request_id=request.request_id,
        jurisdiction_ocdid=request.jurisdiction_ocdid,
        commit_message=request.commit_message,
    )
    if not written:
        raise RuntimeError(f"open-data write rejected for {request.file_path}")
