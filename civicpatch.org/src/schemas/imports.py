"""Request and response models for the sheet importer."""

from pydantic import BaseModel

from core.sheet_import_rows import RowError
from core.roster_diff import ChangeCounts


class ImportPreview(BaseModel):
    """What `parse_rows` found, before anything is written. Pure, so it commits to nothing."""

    jurisdictions_ready: list[str]
    jurisdictions_blocked: list[str]
    rows: int
    errors: list[RowError]


class StartImportResponse(BaseModel):
    batch_id: str
    preview: ImportPreview


class ImportProgress(BaseModel):
    batch_id: str
    status: str
    items_total: int | None
    items_done: int
    error: str | None
    errors: list[RowError]
    rows_read: int | None
    started_at: str
    finished_at: str | None


class ReviewJurisdiction(BaseModel):
    jurisdiction_ocdid: str
    name: str
    changeset_id: str
    changeset_state: str
    # None when counting failed at import; the import itself still landed.
    people: int | None
    change_counts: ChangeCounts | None


class BatchReview(BaseModel):
    batch_id: str
    status: str
    jurisdictions: list[ReviewJurisdiction]


class ChangesetSelection(BaseModel):
    """Which changesets to publish or dismiss. Explicit rather than "everything open": the
    reviewer chose, and the set they saw may be stale by the time they submit."""

    changeset_ids: list[str]


class PublishResult(BaseModel):
    changeset_id: str
    jurisdiction_ocdid: str
    published: bool
    error: str | None = None
