from pydantic import BaseModel

from core.review_summary import ReviewSummary


# Mirrors `services.review_sources.build_sources`.
class ReviewSource(BaseModel):
    url: str
    # Presigned links into the debug bucket; admins only, None for everyone else.
    markdown: str | None
    html: str | None


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
    # Keyed by person id: every claim about a published person, for the per-field badges.
    claims: dict[str, list[dict]]
