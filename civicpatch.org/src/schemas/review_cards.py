from datetime import datetime

from pydantic import BaseModel

from core.review_summary import ReviewSummary


# `services.review_sources.build_sources` returns these.
class ReviewSource(BaseModel):
    url: str
    # Presigned links into the debug bucket; admins only, None for everyone else.
    markdown: str | None
    html: str | None
    # When the pipeline stored the cached page, whether or not it is this scrape's.
    cached_at: datetime | None
    is_cached_by_this_scrape: bool


class ReviewCard(BaseModel):
    """Everything one review card shows. Person rosters stay dicts — see `core/people_roster.py`."""

    changeset_id: str
    jurisdiction_ocdid: str
    existing: list[dict]
    proposed: list[dict]
    sources: list[ReviewSource]
    # Keyed by person id, then field: what the source said where a claim changed it.
    overridden_source_values: dict[str, dict]
    review: ReviewSummary
    # The jurisdiction's organizations, each with its posts — `GET /organizations/{ocdid}`'s shape.
    organizations: list[dict]
    # Which of them this changeset read a page for; the rest of the card's people are older evidence.
    organizations_read: list[str]
    # Keyed by person id: every claim about a published person, for the per-field badges.
    claims: dict[str, list[dict]]
