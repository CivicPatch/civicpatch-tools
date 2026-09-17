"""Which extraction runs a page gets, one per organization. Pure: organizations in, scopes out."""

from typing import List

from pydantic import BaseModel
from services.open_router.prompts import PromptOrganization
from shared.schemas import KnownOrganization


class ExtractionScope(BaseModel):
    """One extraction run: the organization its records are stamped with, and what the prompt is told.

    `prompt_organization` is None when the prompt runs unscoped.
    """

    organization_id: str | None = None
    prompt_organization: PromptOrganization | None = None


def extraction_scopes(organizations: List[KnownOrganization]) -> List[ExtractionScope]:
    """One unscoped run unless there are several organizations to tell apart.

    A single organization keeps today's unscoped prompt — the scoped prompt and its pick list are only
    measured on the org-scoped eval cases — but its records still carry the organization's id. Scoping
    turns on once a maintainer has created a second organization.
    """
    if not organizations:
        return [ExtractionScope()]
    if len(organizations) == 1:
        return [ExtractionScope(organization_id=organizations[0].id)]
    return [
        ExtractionScope(
            organization_id=organization.id,
            prompt_organization=PromptOrganization(
                name=organization.name, posts=[post.label for post in organization.posts]
            ),
        )
        for organization in organizations
    ]
