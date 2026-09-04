import database.change_logs as change_logs_db
import database.changesets as changesets_db
import database.jurisdictions as jurisdictions_db
import database.memberships as memberships_db
import database.pipeline_runs as pipeline_runs_db
import database.review_session_entries as review_session_entries_db
import services.sinks.parquet as parquet_sink
import services.open_data_sync as data_sync
import services.publish as publish_service
import services.sinks.open_data as open_data_sink
import services.sinks.sheet as sheet_sink
from database.issues import upsert_issue
from lib.temporal.types import (
    OpenDataBatchCommitRequest,
    OpenDataCommitItem,
)
from services import entry_sheet
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
    """Render every jurisdiction in the batch and write the changed ones as one commit.

    Raises on failure so Temporal retries, including when another commit won the branch in
    between: the next attempt re-reads the ref and re-renders, so it lands on top rather than
    over the top. A batch with nothing left to write is not a failure — the sweep re-selects
    the same change three times over its lookback, so this is the ordinary outcome twice.
    """
    commit_url = await open_data_sink.commit_rendered_files(
        request.items, request.commit_message
    )
    if commit_url is None:
        activity.logger.info(
            "open-data batch %s: %d jurisdiction(s) already current, nothing committed",
            request.batch_id,
            len(request.items),
        )


# Named so a backstop commit is legible in open-data's history as one — it is the only thing
# that writes without a change_log behind it.
_BACKSTOP_BATCH_ID = "backstop"


@activity.defn
async def backstop_open_data_activity() -> None:
    """Re-render every jurisdiction that has a roster, one batch per state.

    Both mirrors only ever see what `change_logs` reports. A write path that skips the feed, or
    an activity that fails non-retryably, leaves a file stale with nothing to notice — this is
    the only thing that does. It is affordable because of the content gate: a state where
    nothing drifted renders, hashes, matches and makes no API call at all.

    Per state rather than one batch. A single batch naming every jurisdiction would be a Temporal
    payload of thousands of items, and one state's failure would take every other state with it.
    """
    # avoid circular import: the client imports the workflows module, which imports this one
    import lib.temporal.client as temporal_client

    for state in await jurisdictions_db.get_states_with_names():
        code = state["code"]
        ocdids = await memberships_db.jurisdictions_with_rosters(code)
        if not ocdids:
            continue
        await temporal_client.enqueue_open_data_batch_commit(
            OpenDataBatchCommitRequest(
                batch_id=f"{_BACKSTOP_BATCH_ID}:{code}",
                # No changeset ids: nothing here is a changeset landing, so there is no
                # `change_url` to stamp. A backstop corrects drift; it does not publish.
                items=[
                    OpenDataCommitItem(
                        file_path=open_data_sink.reviewed_file_path(ocdid),
                        changeset_ids=[],
                        jurisdiction_ocdid=ocdid,
                    )
                    for ocdid in ocdids
                ],
                commit_message=f"Backstop {code.upper()}",
            )
        )
    activity.logger.info("Backstop: queued open-data for every state with a roster")


@activity.defn
async def backstop_roster_sheets_activity() -> None:
    """Re-sync every state's tabs, whether or not `change_logs` mentioned them.

    Same reasoning as the open-data backstop, and the same reason it is cheap now: an unchanged
    tab costs one streamed hash pass and no Sheets request.
    """
    # avoid circular import: the client imports the workflows module, which imports this one
    import lib.temporal.client as temporal_client

    states = [row["code"] for row in await jurisdictions_db.get_states_with_names()]
    for state in states:
        await temporal_client.enqueue_roster_sheet_sync(state)
    activity.logger.info("Backstop: queued sheet sync for %d state(s)", len(states))


@activity.defn
async def sync_roster_parquet_activity() -> None:
    """The roster as parquet, once a day: every state, every table, to R2.

    Last in `SweepEverythingWorkflow` and with bounded retries, both deliberately — see that
    workflow's docstring. Nothing is waiting on this; the two mirrors ahead of it are.
    """
    tables = await parquet_sink.sync_all()
    activity.logger.info(
        "Roster parquet: %d rows across %d tables",
        sum(t["rows"] for t in tables.values()),
        len(tables),
    )


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
    people, seats, posts = await sheet_sink.sync_state(state)
    activity.logger.info(
        "Sheet sync %s: people %s, memberships %s, posts %s",
        state,
        sheet_sink.describe(people),
        sheet_sink.describe(seats),
        sheet_sink.describe(posts),
    )


@activity.defn
async def sync_jurisdictions_sheet_activity() -> None:
    """Rewrite the all-states dropdown source."""
    written = await sheet_sink.sync_jurisdictions()
    activity.logger.info(
        "Sheet sync jurisdictions: %s", sheet_sink.describe(written)
    )


# Wider than the 5-minute cadence: a redundant re-sync is a no-op, a missed one is a stale tab.
_SWEEP_LOOKBACK_MINUTES = 15

# Not a reviewer's batch. The workflow id is this plus a digest of what was selected, so
# two sweeps covering the same changesets dedupe and a different selection does not.
_SWEEP_BATCH_ID = "sweep"


@activity.defn
async def sweep_open_data_activity() -> None:
    """Commit every jurisdiction that changed recently, as **one** commit.

    The same feed the sheet runs on, read at open-data's grain: one file per jurisdiction
    rather than one tab per state. Derived, not dispatched — a write path that never heard of
    open-data still reaches it, which is what `DELETE /people` and the two post routes needed.

    Repeated sweeps coalesce on their own: the batch workflow's id carries a digest of the
    changesets covered, so the same selection arriving again is `USE_EXISTING`. That is what
    absorbs the lookback window being wider than the cadence.
    """
    # avoid circular import: the client imports the workflows module, which imports this one
    import lib.temporal.client as temporal_client

    changed = await change_logs_db.jurisdictions_changed_since(_SWEEP_LOOKBACK_MINUTES)
    if not changed:
        return
    await temporal_client.enqueue_open_data_batch_commit(
        OpenDataBatchCommitRequest(
            batch_id=_SWEEP_BATCH_ID,
            items=[
                OpenDataCommitItem(
                    file_path=open_data_sink.reviewed_file_path(
                        jurisdiction.jurisdiction_ocdid
                    ),
                    changeset_ids=jurisdiction.changeset_ids,
                    jurisdiction_ocdid=jurisdiction.jurisdiction_ocdid,
                )
                for jurisdiction in changed
            ],
            commit_message=f"Update {len(changed)} jurisdiction(s)",
        )
    )
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
