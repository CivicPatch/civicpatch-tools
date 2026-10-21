"""Starting a collector's runs: one jurisdiction, or a state's claim of the next due. The only
piece that differs by kind is which jurisdictions are due."""

import database.governing_law as governing_law_db
import database.jurisdictions as jurisdictions_db
import database.pipeline_runs as pipeline_runs_db
import lib.temporal.client as temporal_service
import shared.utils.id_utils
from database.governing_law import CollectionCandidate
from pydantic import BaseModel
from shared.utils.statuses import PipelineRunKind

CANDIDATES = {
    PipelineRunKind.GOVERNING_LAW_COLLECTOR: governing_law_db.get_collection_candidates,
    PipelineRunKind.ORGANIZATIONS_COLLECTOR: governing_law_db.get_organizations_collection_candidates,
}


class ClaimedRun(BaseModel):
    jurisdiction_ocdid: str
    pipeline_run_id: str
    name: str


class UnknownJurisdiction(Exception):
    pass


class AlreadyCollecting(Exception):
    pass


async def _register(kind: PipelineRunKind, candidate: CollectionCandidate, created_by_user_id: str | None) -> ClaimedRun:
    run_id = shared.utils.id_utils.make_id()
    await pipeline_runs_db.register_run(
        run_id=run_id,
        kind=kind,
        jurisdiction_ocdid=candidate.jurisdiction_ocdid,
        arguments_json={"jurisdiction_ocdid": candidate.jurisdiction_ocdid, "name": candidate.name},
        created_by_user_id=created_by_user_id,
    )
    return ClaimedRun(jurisdiction_ocdid=candidate.jurisdiction_ocdid, pipeline_run_id=run_id, name=candidate.name)


async def claim_jurisdictions(kind: PipelineRunKind, state: str, num_jurisdictions: int | None, created_by_user_id: str | None) -> list[ClaimedRun]:
    """Select and register in one call: registering is what takes a jurisdiction out of the
    candidates, so a retry after a partial failure resumes instead of doubling."""
    candidates = await CANDIDATES[kind](state, num_jurisdictions)
    return [await _register(kind, candidate, created_by_user_id) for candidate in candidates]


async def start_collection(kind: PipelineRunKind, jurisdiction_ocdid: str, created_by_user_id: str | None, dispatch_mode: str) -> ClaimedRun:
    """One jurisdiction, collected now whatever its last collection's age."""
    name = await jurisdictions_db.get_active_jurisdiction_name(jurisdiction_ocdid)
    if name is None:
        raise UnknownJurisdiction(jurisdiction_ocdid)
    if await pipeline_runs_db.has_unfinished_run(jurisdiction_ocdid, kind):
        raise AlreadyCollecting(jurisdiction_ocdid)
    claimed = await _register(kind, CollectionCandidate(jurisdiction_ocdid=jurisdiction_ocdid, name=name), created_by_user_id)
    await temporal_service.start_collector_workflow(kind, jurisdiction_ocdid, claimed.pipeline_run_id, dispatch_mode)
    return claimed
