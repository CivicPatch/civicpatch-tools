"""Retiring work that time, or a newer arrival, made irrelevant.

Three things that all end the same way — a run that never finished, a review session nobody
came back to, a changeset a later scrape replaced. `expire_stale_*` and `purge_stale_*` are the
codebase's own verbs for this; `supersede` is the odd one out, since displacement is not a
timeout, but it retires a card that stopped mattering just the same.

Split out of the old single `activities.py` on 2026-09-05: none of this touches a sink, and
none of it should pay for importing one.
"""

import database.dismissals as dismissals_db
import database.pipeline_runs as pipeline_runs_db
import database.review_session_entries as review_session_entries_db
from database.issues import upsert_issue
from shared.utils.statuses import PipelineIssueType
from shared.utils.timeouts import PEOPLE_COLLECTOR_EXECUTION_TIMEOUT
from temporalio import activity

# A run that dies before send_error uploads is expired to ERROR with no issue of its own.
# Raise the same generic-failure issue the collector raises (PIPELINE_ERROR), so the
# jurisdiction lands in `blocked` (excluded by jurisdiction_ocdids_with_pending_issues) instead of
# silently re-queuing forever.
_STALE_RUN_ISSUE_DETAIL = {"error": "pipeline run timed out and was expired"}


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
    # Keyed on the proposal when there is one, so the issue resolves to a jurisdiction; else on
    # the run, which the issues page falls back to rendering.
    for run in expired:
        await upsert_issue(
            run.changeset_id or run.pipeline_run_id,
            PipelineIssueType.PIPELINE_ERROR,
            [_STALE_RUN_ISSUE_DETAIL],
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
async def supersede_stacked_requests_activity() -> None:
    dismissed = await dismissals_db.supersede_stacked_requests()
    if dismissed:
        activity.logger.info(
            "Superseded %d stacked request(s): %s", len(dismissed), dismissed
        )
