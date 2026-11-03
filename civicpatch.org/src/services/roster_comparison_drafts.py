"""Batched uploads: start a draft, add rows, finish it into a run through the same service as a
one-shot upload. For agents that upload through MCP tools instead of `curl`."""

from core.roster_comparison_jurisdictions import ocdids_of
from database.jurisdictions import get_state_jurisdictions
import database.roster_comparison_drafts as database
import services.roster_comparison as runs
from schemas.roster_comparisons import (
    MAX_ROWS,
    IncomingRow,
    ResolvedUpload,
    RosterComparisonCreated,
    RosterComparisonDraft,
    RosterComparisonHeader,
)


class DraftNotFound(LookupError):
    def __init__(self, draft_id: str):
        super().__init__(f"No draft {draft_id}: it may have expired, been finished, or belong to someone else.")


class DraftTooLarge(ValueError):
    def __init__(self):
        super().__init__(f"A comparison takes at most {MAX_ROWS} rows.")


class DraftIsEmpty(ValueError):
    def __init__(self):
        super().__init__("Add rows before finishing the draft.")



async def start_draft(header: RosterComparisonHeader, owner_user_id: str) -> RosterComparisonDraft:
    return await database.insert_roster_comparison_draft(owner_user_id, header)


async def add_draft_rows(draft_id: str, rows: list[IncomingRow], owner_user_id: str) -> RosterComparisonDraft:
    header = await database.get_roster_comparison_draft_header(draft_id, owner_user_id)
    if header is None:
        raise DraftNotFound(draft_id)
    # Resolved per batch, so the agent fixes a row now rather than learning at finish.
    jurisdictions = await get_state_jurisdictions(header.state, header.level)
    resolved = await runs.resolve_incoming_rows(header.state, rows, jurisdictions, owner_user_id)
    draft = await database.append_roster_comparison_draft_rows(draft_id, owner_user_id, resolved, MAX_ROWS)
    if draft is not None:
        return draft
    # The update refuses both a missing draft and one that would pass the cap; tell them apart.
    if await database.get_roster_comparison_draft(draft_id, owner_user_id) is None:
        raise DraftNotFound(draft_id)
    raise DraftTooLarge()


async def finish_draft(draft_id: str, owner_user_id: str, corrections: list[str]) -> RosterComparisonCreated:
    draft = await database.get_roster_comparison_draft(draft_id, owner_user_id)
    if draft is None:
        raise DraftNotFound(draft_id)
    header, rows, _ = draft
    if not rows:
        raise DraftIsEmpty()
    upload = ResolvedUpload(**header.model_dump(), corrections=corrections, rows=rows)
    state_ocdids = ocdids_of(await get_state_jurisdictions(header.state, header.level))
    run_id = await runs.compare_and_save(upload, state_ocdids, owner_user_id)
    await database.delete_roster_comparison_draft(draft_id)
    return await runs.get_run_created(run_id)
