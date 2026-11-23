"""Applying a run's reported status: store it, settle what it minted, tell the page.

One path, so an ingest failure and a pipeline failure settle the same way. The rules it applies
are in `core/pipeline_runs`; this is only the I/O.
"""

import json
import logging
from typing import Optional

import lib.pubsub as pubsub_service
from core.pipeline_run_issues.failures import settled_run_issue
from core.pipeline_runs import dismissal_for, is_final
from database.activity import create_activity_row
from database.issues import supersede_prior_jurisdiction_issues, upsert_issue
from database.pipeline_runs import get_pipeline_run, update_pipeline_run_status
from database.publications import dismiss_changeset
from shared.utils.statuses import ActivityType, PipelineIssueType

logger = logging.getLogger(__name__)


async def finalize_pipeline_run(
    changeset_id: Optional[str], status: str, jurisdiction_ocdid: Optional[str]
) -> None:
    """A run ended. Settle the proposal it minted, if it got that far.

    Takes the changeset, not the run: their ids diverged at migration 169, so passing the run's
    matched no row and both branches were silent no-ops.
    """
    # It minted nothing, so there is nothing to settle and nothing it replaced.
    if changeset_id is None:
        return

    reason = dismissal_for(status)
    if reason:
        await dismiss_changeset(changeset_id, reason)

    if jurisdiction_ocdid:
        await supersede_prior_jurisdiction_issues(jurisdiction_ocdid, changeset_id)


async def apply_pipeline_run_status(
    pipeline_run_id: str,
    status: str,
    progress: Optional[int],
    jurisdiction_ocdid: Optional[str],
    error_type: Optional[str] = None,
    error_detail: Optional[dict] = None,
):
    """A run reported a status: store it, settle it if it is over, tell the page.

    Not "publish", which everywhere else means a roster going live.
    """
    # A run killed without reporting files its failure here, and how far it got is what explains
    # it — the update below writes over that.
    last_seen = (
        await get_pipeline_run(pipeline_run_id) if error_type and is_final(status) else None
    )
    applied = await update_pipeline_run_status(
        run_id=pipeline_run_id, status=status, progress=progress
    )
    # The run was already settled. Reporting is best-effort and the pipeline keeps going after a
    # cancel, so this is ordinary — but everything below settles the changeset and tells the
    # page a run is live, and neither is true a second time.
    if not applied:
        logger.info(
            "Ignoring %s for pipeline run %s: it is already finished",
            status,
            pipeline_run_id,
        )
        return

    # The run's row knows the jurisdiction and the changeset; a report arrives every loop, so
    # read it only when one of them is needed.
    final = is_final(status)
    pipeline_run = None
    if not jurisdiction_ocdid or final:
        pipeline_run = await get_pipeline_run(pipeline_run_id)

    if not jurisdiction_ocdid and pipeline_run:
        jurisdiction_ocdid = pipeline_run["jurisdiction_ocdid"]

    if final:
        changeset_id = pipeline_run.get("changeset_id") if pipeline_run else None
        await finalize_pipeline_run(changeset_id, status, jurisdiction_ocdid)
        if error_type:
            await _file_run_failure(pipeline_run_id, error_type, error_detail, last_seen)
        # Best-effort, its own connection: this settles beside a report that already committed
        # above, not inside it. `changeset_id` is set only when the run reached ingest — a
        # failed or cancelled run mints none. Caught rather than left to propagate: the report
        # itself already succeeded, so a broken activity write must not read back as a failed
        # status update.
        try:
            await create_activity_row(
                ActivityType.PIPELINE_RUN_END,
                user_id=None,
                jurisdiction_ocdid=jurisdiction_ocdid,
                changeset_id=changeset_id,
            )
        except Exception:
            logger.exception(f"[{pipeline_run_id}] Failed to log pipeline_run_end activity")

    if jurisdiction_ocdid:
        # Best-effort: the status update above already committed, so a Redis hiccup here must
        # not make an otherwise-successful report look like a failure to the caller.
        try:
            await pubsub_service.publish(
                pubsub_service.pipeline_run_status_channel(jurisdiction_ocdid),
                json.dumps(
                    {
                        "pipeline_run_id": pipeline_run_id,
                        "status": status,
                        "progress": progress,
                        # Derived here so a live update and a fetched row cannot disagree.
                        "is_running": not final,
                    }
                ),
            )
        except Exception:
            logger.exception(
                f"[{pipeline_run_id}] Failed to announce "
                f"{pubsub_service.pipeline_run_status_channel(jurisdiction_ocdid)}"
            )


async def _file_run_failure(
    pipeline_run_id: str,
    error_type: str,
    error_detail: Optional[dict],
    last_seen: Optional[dict],
) -> None:
    """The run that reached no report and so filed nothing: the workflow settled it, so the issue
    has to be made here. Filing is best-effort, because the status update beside it has already
    committed.
    """
    issue = settled_run_issue(error_type, error_detail, last_seen)
    try:
        await upsert_issue(pipeline_run_id, issue.issue_type, [issue.data])
    except Exception:
        logger.exception(f"[{pipeline_run_id}] Failed to file {issue.issue_type}")
