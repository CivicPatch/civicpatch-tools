"""Applying a run's reported status: store it, settle what it minted, tell the page.

One path, so an ingest failure and a pipeline failure settle the same way. The rules it applies
are in `core/pipeline_runs`; this is only the I/O.
"""

import json
from typing import Optional

import lib.pubsub as pubsub_service
from core.pipeline_runs import dismissal_for, is_final
from database.issues import supersede_prior_jurisdiction_issues
from database.pipeline_runs import get_pipeline_run, update_pipeline_run_status
from database.publications import dismiss_request


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
        await dismiss_request(changeset_id, reason)

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
    await update_pipeline_run_status(
        run_id=pipeline_run_id, status=status, progress=progress
    )

    # The run's row knows the jurisdiction and the changeset; a report arrives every loop, so
    # read it only when one of them is needed.
    final = is_final(status)
    pipeline_run = None
    if not jurisdiction_ocdid or final:
        pipeline_run = await get_pipeline_run(pipeline_run_id)

    if not jurisdiction_ocdid and pipeline_run:
        jurisdiction_ocdid = (pipeline_run.get("arguments_json") or {}).get(
            "jurisdiction_ocdid"
        )

    if final:
        await finalize_pipeline_run(
            pipeline_run.get("changeset_id") if pipeline_run else None,
            status,
            jurisdiction_ocdid,
        )

    if jurisdiction_ocdid:
        await pubsub_service.publish(
            f"pipeline_run_status:{jurisdiction_ocdid}",
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
