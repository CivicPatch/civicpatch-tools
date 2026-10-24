"""Batched uploads: start a draft, add rows, finish it into a run through the same service as a
one-shot upload. For agents that upload through MCP tools instead of `curl`."""

import database.roster_comparison_drafts as database
import services.roster_comparison as runs
from schemas.roster_comparisons import (
    MAX_ROWS,
    RosterComparisonCreated,
    RosterComparisonDraft,
    RosterComparisonHeader,
    RosterComparisonUpload,
    UploadedRow,
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


async def add_draft_rows(draft_id: str, rows: list[UploadedRow], owner_user_id: str) -> RosterComparisonDraft:
    state = await database.get_roster_comparison_draft_state(draft_id, owner_user_id)
    if state is None:
        raise DraftNotFound(draft_id)
    # Checked per batch, so the agent fixes it now rather than learning at finish.
    await runs.check_rows_in_state(state, rows, owner_user_id)
    draft = await database.append_roster_comparison_draft_rows(draft_id, owner_user_id, rows, MAX_ROWS)
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
    upload = RosterComparisonUpload(**header.model_dump(), corrections=corrections, rows=rows)
    run_id = await runs.run_roster_comparison(upload, owner_user_id)
    await database.delete_roster_comparison_draft(draft_id)
    return await runs.get_run_created(run_id)
