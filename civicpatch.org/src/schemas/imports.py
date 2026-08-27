"""Request and response models for the sheet importer."""

from pydantic import BaseModel

from core.entry_rows import RowError


class ImportPreview(BaseModel):
    """What `parse_rows` found, before anything is written. Pure, so it commits to nothing."""

    jurisdictions_ready: list[str]
    jurisdictions_blocked: list[str]
    jurisdictions_skipped: list[str]
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
    started_at: str
    finished_at: str | None
