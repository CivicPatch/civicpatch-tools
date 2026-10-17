from typing import List

import services.open_router.prompts as open_router_prompt
from runners.people_collector.schemas import ExpectedMembership
from runners.people_collector.steps.step_04_process_page_content.extraction_by_organization import (
    ExtractionScope,
    extraction_scopes,
    prompt_organization,
)
from shared.schemas import KnownOrganization, PipelineRunConfig
from shared.utils import id_utils
from shared.utils.content_hash import hash_texts
from runners.people_collector.utils.organization_terms import (
    expected_divisions,
    expected_roles,
    government_form_role_labels,
)


def prompt_hash(
    page_url: str,
    config: PipelineRunConfig,
    jurisdiction_ocdid: str,
    known_roles: List[str],
    organizations: List[KnownOrganization],
    memberships: List[ExpectedMembership],
) -> str:
    """Everything the LLM sees about this page besides its text: every prompt it could be sent,
    rendered by the same builders the calls use, so any input or wording change moves it.
    Hashing a prompt a run never sends is harmless: it can only force a re-read."""
    prompts = [relevance_prompt(page_url, config, known_roles, organizations)]
    prompts += [coverage_prompt(organization, memberships, config) for organization in organizations]
    prompts += [
        extraction_prompt(organizations, memberships, jurisdiction_ocdid, scope)
        for scope in extraction_scopes(organizations, memberships)
    ]
    return hash_texts(prompts)


def relevance_prompt(
    page_url: str,
    config: PipelineRunConfig,
    known_roles: List[str],
    organizations: List[KnownOrganization],
) -> str:
    return open_router_prompt.relevant_page_prompt(
        page_url,
        config.name or "",
        known_roles,
        [organization.name for organization in organizations],
        government_form=config.government_form,
    )


def coverage_prompt(
    organization: KnownOrganization, memberships: List[ExpectedMembership], config: PipelineRunConfig
) -> str:
    asked = prompt_organization(organization, memberships)
    return open_router_prompt.page_covers_organization_prompt(
        organization.name,
        asked.role_labels,
        config.name or "",
        divisions=asked.divisions,
        government_form_role_labels=asked.government_form_role_labels,
    )


def extraction_prompt(
    organizations: List[KnownOrganization],
    memberships: List[ExpectedMembership],
    jurisdiction_ocdid: str,
    scope: ExtractionScope,
) -> str:
    """An unscoped run is told the whole jurisdiction's roles and divisions; a scoped one reads
    its organization's from `scope`."""
    ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    return open_router_prompt.elected_officials_prompt(
        expected_roles(memberships),
        state=ocdid_parts.state,
        county=ocdid_parts.county,
        organization=scope.prompt_organization,
        divisions=expected_divisions(memberships),
        government_form_role_labels=government_form_role_labels(organizations, memberships),
    )
