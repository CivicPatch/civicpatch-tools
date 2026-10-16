"""What happened to each page a scrape read. Pure: a `source_pages` row in, its outcome out."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class PageOutcome(StrEnum):
    READ = "read"
    UNCHANGED = "unchanged"
    NOT_ABOUT_OFFICIALS = "not_about_officials"
    EXTRACTION_FAILED = "extraction_failed"
    FAILED_TO_LOAD = "failed_to_load"


class ScrapePageRow(BaseModel):
    jurisdiction_ocdid: str
    pipeline_run_id: str
    source_url: str
    page_hash: str | None
    is_relevant: bool | None
    heuristics_failures: list[str]
    unchanged_since: datetime | None
    organization_names: list[str]
    people_count: int


class ScrapePage(BaseModel):
    source_url: str
    outcome: PageOutcome
    unchanged_since: datetime | None
    organization_names: list[str]
    people_count: int
    # The pipeline's cached copies: admins only, so None for everyone else.
    markdown_url: str | None = None
    html_url: str | None = None


def page_outcome(row: ScrapePageRow) -> PageOutcome:
    if row.unchanged_since is not None:
        return PageOutcome.UNCHANGED
    if row.page_hash is None:
        return PageOutcome.FAILED_TO_LOAD
    if row.is_relevant is False:
        return PageOutcome.NOT_ABOUT_OFFICIALS
    if row.heuristics_failures and row.people_count == 0:
        return PageOutcome.EXTRACTION_FAILED
    return PageOutcome.READ


def scrape_page(row: ScrapePageRow) -> ScrapePage:
    return ScrapePage(
        source_url=row.source_url,
        outcome=page_outcome(row),
        unchanged_since=row.unchanged_since,
        organization_names=row.organization_names,
        people_count=row.people_count,
    )
