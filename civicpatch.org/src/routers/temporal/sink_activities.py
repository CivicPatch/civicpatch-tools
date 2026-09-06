"""Outbound: the database rendered into the three mirrors — the sheet, open-data, and parquet.

`services/sinks/` is the machinery; this is the Temporal-facing seam onto it. Everything here
writes outward, which is what separates it from `jurisdiction_activities` — a distinction
`AGENTS.md:40-41` makes deliberately and this split now makes structural.

This is also where the memory is: a sweep peaks at 253Mi because these activities materialise
whole tables. That is why the sinks worker is the one with a concurrency cap.

Split out of the old single `activities.py` on 2026-09-05.
"""

import database.change_logs as change_logs_db
import database.jurisdictions as jurisdictions_db
import database.memberships as memberships_db
import services.sinks.open_data as open_data_sink
import services.sinks.parquet as parquet_sink
import services.sinks.sheet as sheet_sink
from lib.temporal.types import (
    OpenDataBatchCommitRequest,
    OpenDataCommitItem,
)
from services import entry_sheet
from temporalio import activity


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
async def backstop_open_data_activity(state: str) -> None:

    ocdids = await memberships_db.jurisdictions_with_rosters(state)
    if not ocdids:
        return
    committed = await open_data_sink.commit_rendered_files(
        [
            OpenDataCommitItem(
                file_path=open_data_sink.reviewed_file_path(ocdid),
                # No changeset ids: nothing here is a changeset landing, so there is no
                # `change_url` to stamp. A backstop corrects drift; it does not publish.
                changeset_ids=[],
                jurisdiction_ocdid=ocdid,
            )
            for ocdid in ocdids
        ],
        f"Backstop {state.upper()}",
    )
    activity.logger.info(
        "Backstop %s: %d jurisdiction(s) checked, %s",
        state,
        len(ocdids),
        "nothing to commit" if committed is None else committed,
    )


@activity.defn
async def list_states_activity() -> list[str]:
    """Every state we hold, for the backstop to walk one at a time.

    A list, not a fan-out. This used to enqueue a sync workflow per state, and all fifteen then
    raced the same Google Sheets quota — 60 write requests a minute for the whole service
    account, against ~192 requests fired at once. The losers sat in 429 backoff until their
    activity timed out: Colorado, 2,177 rows and twelve requests, died at fifteen minutes
    because it was starved rather than slow.

    Sequencing belongs to the caller, which is why this only reports.
    """
    return [row["code"] for row in await jurisdictions_db.get_states_with_names()]


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
    """Rewrite the all-states dropdown source, then put the tab bar back in order.

    The bar is spreadsheet-wide like this tab is, and re-imposing it costs one read when it is
    already right — so it rides along here rather than earning an activity of its own.
    """
    written = await sheet_sink.sync_jurisdictions()
    activity.logger.info("Sheet sync jurisdictions: %s", sheet_sink.describe(written))

    moved = await sheet_sink.order_tabs()
    activity.logger.info("Sheet tab order: %d tab(s) moved", moved)


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
