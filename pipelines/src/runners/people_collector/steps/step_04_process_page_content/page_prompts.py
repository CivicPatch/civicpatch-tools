from typing import List

import services.open_router.prompts as open_router_prompt
from runners.people_collector.steps.step_04_process_page_content.extraction_scopes import (
    ExtractionScope,
    extraction_scopes,
)
from shared.schemas import KnownOrganization, PipelineRunConfig
from shared.utils import id_utils
from shared.utils.content_hash import hash_texts
from shared.utils.government_forms import office_labels


def prompt_hash(
    page_url: str,
    config: PipelineRunConfig,
    jurisdiction_ocdid: str,
    known_roles: List[str],
    organizations: List[KnownOrganization],
) -> str:
    """Everything the LLM sees about this page besides its text: every prompt it could be sent,
    rendered by the same builders the calls use, so any input or wording change moves it.
    Hashing a prompt a run never sends is harmless: it can only force a re-read."""
    prompts = [relevance_prompt(page_url, config, known_roles, organizations)]
    prompts += [coverage_prompt(organization, config) for organization in organizations]
    prompts += [
        extraction_prompt(known_roles, jurisdiction_ocdid, scope)
        for scope in extraction_scopes(organizations)
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


def coverage_prompt(organization: KnownOrganization, config: PipelineRunConfig) -> str:
    return open_router_prompt.page_covers_organization_prompt(
        organization.name,
        office_labels(organization),
        config.name or "",
    )


def extraction_prompt(
    known_roles: List[str], jurisdiction_ocdid: str, scope: ExtractionScope
) -> str:
    ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    return open_router_prompt.municipality_officials_prompt(
        known_roles,
        state=ocdid_parts.state,
        county=ocdid_parts.county,
        organization=scope.prompt_organization,
    )
