"""Request and response models for the sheet importer."""

from pydantic import BaseModel

from core.entry_rows import RowError


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
    started_at: str
    finished_at: str | None


class ReviewPerson(BaseModel):
    """Everything the sheet supplied for this person, as it will be written.

    Wider than the first cut, which showed name and seat only: a reviewer approving a bulk
    import is approving the phone numbers and emails too, and cannot approve what they cannot
    see. Lists because a person reconciled from several sightings can carry more than one.
    """

    id: str
    name: str
    label: str
    image: str | None = None
    urls: list[str] = []
    phones: list[str] = []
    emails: list[str] = []
    start_date: str | None = None
    end_date: str | None = None
    # None when no label resolved to a role. `unmatched_text` is the wording that did not
    # resolve, which is what a curator would need to fix in the sheet.
    role_id: str | None = None
    unmatched_text: list[str] = []


class ReviewJurisdiction(BaseModel):
    jurisdiction_ocdid: str
    name: str
    changeset_id: str
    changeset_state: str
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
