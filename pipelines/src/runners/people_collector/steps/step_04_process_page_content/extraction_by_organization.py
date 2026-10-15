"""Which extraction runs a page gets, one per organization. Pure: organizations in, scopes out."""

from typing import List

from pydantic import BaseModel
from runners.people_collector.schemas import ExpectedMembership
from runners.people_collector.utils.organization_terms import (
    expected_divisions,
    expected_roles,
    memberships_in,
)
from services.open_router.prompts import PromptOrganization
from shared.schemas import KnownOrganization


class ExtractionScope(BaseModel):
    """One extraction run. `prompt_organization` None runs the prompt unscoped."""

    organization_id: str | None = None
    prompt_organization: PromptOrganization | None = None


def prompt_organization(
    organization: KnownOrganization, memberships: List[ExpectedMembership]
) -> PromptOrganization:
    """The form's role labels only when we expect nobody in it: they are a guess."""
    own = memberships_in(organization.id, memberships)
    return PromptOrganization(
        name=organization.name,
        role_labels=expected_roles(own),
        divisions=expected_divisions(own),
        government_form_role_labels=[] if own else organization.role_labels,
    )


def extraction_scopes(
    organizations: List[KnownOrganization],
    memberships: List[ExpectedMembership],
    covers: List[str] | None = None,
) -> List[ExtractionScope]:
    """One run per organization the page covers; a lone organization runs unscoped.
    `covers` None or empty means unknown, so every organization runs."""
    if not organizations:
        return [ExtractionScope()]
    if len(organizations) == 1:
        return [ExtractionScope(organization_id=organizations[0].id)]
    named = [organization for organization in organizations if organization.name in (covers or [])]
    return [
        ExtractionScope(
            organization_id=organization.id,
            prompt_organization=prompt_organization(organization, memberships),
        )
        for organization in (named or organizations)
    ]
