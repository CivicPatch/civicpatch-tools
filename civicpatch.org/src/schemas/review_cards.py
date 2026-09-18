from pydantic import BaseModel

from core.membership_proposal import ProposedChange
from core.review_summary import ReviewSummary


# Mirrors `services.review_sources.build_sources`.
class ReviewSource(BaseModel):
    url: str
    markdown: str | None


class ReviewCard(BaseModel):
    """Everything one review card shows. Person rosters stay dicts — see `core/people_roster.py`."""

    changeset_id: str
    jurisdiction_ocdid: str
    existing: list[dict]
    proposed: list[dict]
    changes: list[ProposedChange]
    sources: list[ReviewSource]
    # Keyed by person id, then field: what the source said where an assertion changed it.
    overridden_source_values: dict[str, dict]
    review: ReviewSummary
    # The jurisdiction's organizations, each with its posts — `GET /organizations/{ocdid}`'s shape.
    organizations: list[dict]
    # Keyed by person id: every assertion about a published person, for the per-field badges.
    assertions: dict[str, list[dict]]
