from typing import List

import services.open_router.prompts as open_router_prompt
from runners.pipeline03_people_collector.schemas import ExpectedMembership
from shared.schemas import KnownOrganization, PipelineRunConfig
from runners.pipeline03_people_collector.steps.step_04_process_page_content.organization_match import without_default
from shared.utils import id_utils
from shared.utils.content_hash import hash_texts
from runners.pipeline03_people_collector.utils.organization_terms import (
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
    return hash_texts(
        [
            relevance_prompt(page_url, config, known_roles, organizations),
            page_extraction_prompt(organizations, memberships, jurisdiction_ocdid),
        ]
    )


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


def page_extraction_prompt(
    organizations: List[KnownOrganization],
    memberships: List[ExpectedMembership],
    jurisdiction_ocdid: str,
) -> str:
    """One unscoped read of the page; each person's organization is picked from ours."""
    ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    return open_router_prompt.elected_officials_prompt(
        expected_roles(memberships),
        level=ocdid_parts.level,
        state=ocdid_parts.state,
        county=ocdid_parts.county,
        divisions=expected_divisions(memberships),
        government_form_role_labels=government_form_role_labels(organizations, memberships),
        organization_choices=[organization.name for organization in without_default(organizations)],
    )
