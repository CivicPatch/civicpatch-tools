import database.pipeline_runs as pipeline_runs_db
import database.changesets as changesets_db
import database.review_session_entries as review_session_entries_db
import lib.github.api as github_service
import services.open_data_sync as data_sync
import services.publish as publish_service
from database.issues import upsert_issue
from lib.temporal.types import OpenDataBatchCommitRequest, OpenDataCommitRequest
from shared.utils.statuses import PipelineIssueType
from shared.utils.timeouts import PEOPLE_COLLECTOR_EXECUTION_TIMEOUT
from temporalio import activity

# A run that dies before send_error uploads is expired to ERROR with no issue of its own.
# Raise the same generic-failure issue the collector raises (PIPELINE_ERROR), so the
# jurisdiction lands in `blocked` (excluded by get_pending_issue_ocdids) instead of
# silently re-queuing forever.
_STALE_RUN_ISSUE_DETAIL = {"error": "pipeline run timed out and was expired"}


@activity.defn
async def od_sync_activity() -> None:
    await data_sync.sync_all()


@activity.defn
async def od_sync_targeted_activity(jurisdiction_ocdids: list[str]) -> None:
    await data_sync.sync_by_ocdids(jurisdiction_ocdids)


@activity.defn
async def expire_stale_pipeline_runs_activity() -> None:
    expired = await pipeline_runs_db.expire_stale_pipeline_runs(
        PEOPLE_COLLECTOR_EXECUTION_TIMEOUT
    )
    if not expired:
        return
    activity.logger.warning(
        "Expired %d stale pipeline run(s): %s", len(expired), expired
    )
    for request_id in expired:
        await upsert_issue(
            request_id, PipelineIssueType.PIPELINE_ERROR, [_STALE_RUN_ISSUE_DETAIL]
        )


@activity.defn
async def cleanup_stale_review_entries_activity() -> None:
    result = await review_session_entries_db.purge_stale_idle_sessions()
    if result["entries_deleted"]:
        activity.logger.info(
            "Review session cleanup: %d entries deleted",
            result["entries_deleted"],
        )


@activity.defn
async def commit_open_data_batch_activity(request: OpenDataBatchCommitRequest) -> None:
    """Render every jurisdiction in the batch and write them to open-data as one commit.

    Raises on failure so Temporal retries, including when another commit won the branch in
    between: the next attempt re-reads the ref and re-renders, so it lands on top rather than
    over the top.
    """
    written = await publish_service.commit_rendered_files(
        request.items, request.commit_message
    )
    if not written:
        raise RuntimeError(
            f"open-data batch write rejected for {request.batch_id} "
            f"({len(request.items)} jurisdictions)"
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
        source=request.source,
    )
    if not written:
        raise RuntimeError(f"open-data write rejected for {request.file_path}")

    # Only after the write landed: a promotion that deleted first would lose the data if the
    # write then failed. Deleting an already-absent file succeeds, so a retry is harmless.
    if request.delete_path:
        removed = await github_service.delete_github_file(
            branch_name=github_service.DEFAULT_BRANCH,
            file_path=request.delete_path,
            commit_message=request.delete_message or f"Remove {request.delete_path}",
        )
        if not removed:
            raise RuntimeError(f"open-data delete rejected for {request.delete_path}")


@activity.defn
async def supersede_stacked_requests_activity() -> None:
    dismissed = await changesets_db.supersede_stacked_requests()
    if dismissed:
        activity.logger.info(
            "Superseded %d stacked request(s): %s", len(dismissed), dismissed
        )
