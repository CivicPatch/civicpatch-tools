"""A reviewer's edits to a scrape's roster, and making that roster live.

Lifted out of `routers/api/pull_requests.py`, where it did not belong twice over: it is
orchestration, which lives here, and it touches no pull request — every entry point is keyed on
`request_id`. That router is on its way out, and this had no reason to go with it.

`data_json` is the roster of record: the reviewer's edits land there and nowhere else, which is
what keeps that column alive. See `.scratch/2026-08-24-assertions-accept-reject.md`.
"""

import logging
from typing import List

import database.pipeline_runs
import services.change_logs as change_logs
from core.people_patch import PersonPatch, patch_people
from schemas.common import Identity
from services.publish import promote_images, promote_to_reviewed, publish_people

logger = logging.getLogger(__name__)


class MissingRoster(Exception):
    """The scrape has no recorded roster, so there is nothing to edit or publish."""


async def save(
    request_id: str,
    jurisdiction_ocdid: str,
    data: List[PersonPatch],
    user: Identity,
) -> List[dict]:
    """Apply the reviewer's edits to the scrape's stored roster."""
    base = await database.pipeline_runs.get_pipeline_run_data_json(request_id)
    if not base:
        raise MissingRoster(request_id)

    patched = patch_people(base, data)

    # Awaited, not backgrounded: this was a background task while the branch write was the
    # authoritative one. It is the only store now, so a 200 must mean the edit is persisted.
    await database.pipeline_runs.update_pipeline_run_data(request_id, patched)
    if user.user_id:
        await change_logs.record_manual_edits(
            request_id, jurisdiction_ocdid, user.user_id, base, patched
        )
    return patched


async def publish(
    request_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str | None,
) -> None:
    """Make this scrape's roster live. `edited` is the reviewer's patched result; when they
    published without editing, the submitted roster stands."""
    roster = edited
    if roster is None:
        roster = await database.pipeline_runs.get_pipeline_run_data_json(request_id)
    # Publishing an empty roster retires every person in the jurisdiction. That was unreachable
    # while the review pool required an open PR; the request is the only record now.
    if not roster:
        raise MissingRoster(request_id)
    # Photos promote with the data: publishing is what moves them off the artifacts bucket.
    await publish_people(
        request_id, jurisdiction_ocdid, promote_images(roster), resolved_by_user_id
    )
    # The scrape leaves the unreviewed path for the canonical one. Queued, so a slow or failed
    # GitHub write cannot affect a publish that has already committed.
    await promote_to_reviewed(request_id, jurisdiction_ocdid)
