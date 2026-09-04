import database.change_logs as change_logs_db
import database.pipeline_runs as pipeline_runs_db
import database.changesets as changesets_db
import database.review_session_entries as review_session_entries_db
import lib.github.api as github_service
import services.open_data_sync as data_sync
import services.publish as publish_service
import services.roster_sheet as roster_sheet
from services import entry_sheet
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
    # Its own workflow, not an activity here: this schedule is SKIP-overlap, so a Sheets write
    # retrying forever would block every later sync.
    #
    # avoid circular import: the client imports the workflows module, which imports this one
    import lib.temporal.client as temporal_client

    if entry_sheet.is_configured():
        await temporal_client.enqueue_jurisdictions_sheet_sync()


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
    for changeset_id in expired:
        await upsert_issue(
            changeset_id, PipelineIssueType.PIPELINE_ERROR, [_STALE_RUN_ISSUE_DETAIL]
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
        changeset_id=request.changeset_id,
        jurisdiction_ocdid=request.jurisdiction_ocdid,
        commit_message=request.commit_message,
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


@activity.defn
async def sync_roster_sheet_activity(state: str) -> None:
    """Rewrite one state's people and posts tabs. Retry-safe: replaced whole, not patched."""
    people, seats, posts = await roster_sheet.sync_state(state)
    activity.logger.info(
        "Sheet sync %s: %d people, %d memberships, %d posts", state, people, seats, posts
    )


@activity.defn
async def sync_jurisdictions_sheet_activity() -> None:
    """Rewrite the all-states dropdown source."""
    written = await roster_sheet.sync_jurisdictions()
    activity.logger.info("Sheet sync jurisdictions: %d rows", written)


# Wider than the 5-minute cadence: a redundant re-sync is a no-op, a missed one is a stale tab.
_SWEEP_LOOKBACK_MINUTES = 15


@activity.defn
async def sweep_open_data_activity() -> None:
    """Commit every jurisdiction that changed recently.

    The same feed the sheet runs on, read at open-data's grain: one file per jurisdiction
    rather than one tab per state. Derived, not dispatched — a write path that never heard of
    open-data still reaches it, which is what `DELETE /people` and the two post routes needed.

    Repeated sweeps of the same jurisdiction coalesce: `enqueue_open_data_commit` keys on the
    file path and the commit re-renders from the database, so a second enqueue is a no-op.
    """
    changed = await change_logs_db.jurisdictions_changed_since(_SWEEP_LOOKBACK_MINUTES)
    for jurisdiction in changed:
        await publish_service.commit_roster(
            jurisdiction.jurisdiction_ocdid,
            f"Update {jurisdiction.jurisdiction_ocdid} "
            f"({', '.join(jurisdiction.change_types)})",
        )
    if changed:
        activity.logger.info("Swept %d jurisdiction(s) into open-data", len(changed))


@activity.defn
async def sweep_roster_sheets_activity() -> None:
    """Sync every state that changed recently. The sheet's only route in during normal running.

    Derived, not dispatched — nothing calls out to the sheet, so a new write path cannot forget
    it without also breaking the jurisdiction history page.

    """
    # avoid circular import: the client imports the workflows module, which imports this one
    import lib.temporal.client as temporal_client

    if not entry_sheet.is_configured():
        return
    states = await change_logs_db.states_changed_since(_SWEEP_LOOKBACK_MINUTES)
    for state in states:
        await temporal_client.enqueue_roster_sheet_sync(state)
    if states:
        activity.logger.info("Swept %s into sheet syncs", ", ".join(states))
