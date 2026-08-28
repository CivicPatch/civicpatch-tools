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


class ReviewPerson(BaseModel):
    """The limited view: enough to scan forty towns, not enough to audit one."""

    id: str
    name: str
    label: str
    image: str | None = None


class ReviewJurisdiction(BaseModel):
    jurisdiction_ocdid: str
    name: str
    request_id: str
    review_status: str
    people: list[ReviewPerson]


class BatchReview(BaseModel):
    batch_id: str
    status: str
    jurisdictions: list[ReviewJurisdiction]


class PublishSelectionRequest(BaseModel):
    """Which towns to publish. Explicit rather than "everything pending": the reviewer chose,
    and the set they saw may be stale by the time they submit."""

    jurisdiction_ocdids: list[str]


class PublishResult(BaseModel):
    jurisdiction_ocdid: str
    published: bool
    error: str | None = None
