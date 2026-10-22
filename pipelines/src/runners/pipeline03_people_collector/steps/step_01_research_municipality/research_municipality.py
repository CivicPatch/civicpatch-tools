"""Step 1 — what we already know about this jurisdiction, before looking at any page.

Two things steer the rest of the run: which names are one person (`identities`), and who we
expect to find (`expected_memberships`), whose roles and divisions are the offices to look for.

Those come off cp.org's `posts`, which is where they are decided. Research is
the cold-start path only, for a jurisdiction with no posts to read them from.
"""

from typing import Dict, List, Optional

import httpx
import services.civicpatch_api as civicpatch_api
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
from pipelines_environment import get_env_vars
from ...schemas import (
    ExpectedMembership,
    PeopleCollectorContext,
    PeopleCollectorState,
    PeopleCollectorStep,
    ResearchMunicipalityStep,
    ResearchedPerson,
)
from shared.schemas import KnownOrganization, Membership, Person, Post, RoleConfig
from ..step_01_research_municipality import government_form
from shared.utils import divisions
from shared.utils.label_parser import parse_label, parse_label_preferring
from shared.utils.taxonomy import UNMATCHED_ROLE_ID, Taxonomy, build_taxonomy
from shared.utils.name_utils import person_list_to_identities
from utils import log_utils
from utils.request_utils import with_retry


async def research_municipality(
    context: PeopleCollectorContext, api_client: httpx.AsyncClient
) -> ResearchMunicipalityStep:
    """What to look for, and which names are one person.

    The split is on posts, not people: a jurisdiction with posts has been scraped before, so
    the offices are already parsed and stored. Only a first scrape researches, and what comes
    back is parsed with the same parser cp.org uses.
    """
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 1: {PeopleCollectorStep.RESEARCH_MUNICIPALITY.value}")

    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    existing = await civicpatch_api.get_active_people(api_client, logger, jurisdiction_ocdid)

    if _can_research() and context.data.config.government_form_choices:
        await government_form.request_government_form(context, api_client, logger)
    # After the form: a form saved just now has already built its organizations.
    organizations = await civicpatch_api.get_organizations(api_client, logger, jurisdiction_ocdid)
    posts = [post for organization in organizations for post in organization.posts]

    researched: List[ResearchedPerson] = []
    if posts:
        logger.info(f"research_municipality: {len(posts)} known posts, skipping research.")
    else:
        researched = await _research_roster(context, organizations, logger) if _can_research() else []

    taxonomy = build_taxonomy(context.data.role_config)
    return ResearchMunicipalityStep(
        researched=researched,
        known_organizations=organizations,
        expected_memberships=(
            _post_memberships(
                posts,
                [membership for person in existing for membership in Person(**person).memberships],
                context.data.role_config,
                jurisdiction_ocdid,
            )
            or _researched_memberships(
                researched, organizations, taxonomy
            )
        ),
        # Whoever cp.org has published, else whoever research named. Separate from the offices
        # above: a jurisdiction can have posts and nobody accepted onto them yet.
        identities=_identities(existing, researched),
        source_urls=await _source_urls(context.data.config, api_client, logger, jurisdiction_ocdid),
    )


def _identities(existing: List[dict], researched: List[ResearchedPerson]) -> Dict[str, List[str]]:
    if existing:
        return person_list_to_identities([Person(**person) for person in existing])
    return {person.name: [] for person in researched}


def _post_memberships(
    posts: List[Post],
    held: List[Membership],
    role_config: RoleConfig | None,
    jurisdiction_ocdid: str,
) -> List[ExpectedMembership]:
    """One per post, carrying the designations of every membership held on it. `unmatched` is
    skipped: it has no label worth searching a page for."""
    taxonomy = build_taxonomy(role_config)
    return [
        ExpectedMembership(
            organization_id=post.organization_id,
            role_label=post.role_label,
            division=_division(post.division_ocdid, jurisdiction_ocdid),
            designations=_designations_held_on(post, held, taxonomy),
        )
        for post in posts
        if post.role_id != UNMATCHED_ROLE_ID
    ]


def _designations_held_on(post: Post, held: List[Membership], taxonomy: Taxonomy) -> List[str]:
    """Read off each membership's label, which a human may have corrected, by the same parser."""
    return list(
        dict.fromkeys(
            designation
            for membership in held
            if membership.post_id == post.id and membership.label
            for designation in parse_label(membership.label, taxonomy).other_designations
        )
    )


def _division(division_ocdid: str, jurisdiction_ocdid: str) -> Optional[str]:
    return _first_division(divisions.division_ocdid_to_designation(division_ocdid, jurisdiction_ocdid))


def _first_division(designations: List[str]) -> Optional[str]:
    found = divisions.filter_divisions(designations)
    return found[0] if found else None


def _organization_for(
    researched_organization: str,
    role_label: str,
    organizations: List[KnownOrganization],
    default: KnownOrganization,
) -> KnownOrganization:
    """The organization research named, if it is one of ours; else the one whose role labels
    include this role; else the default."""
    for organization in organizations:
        if organization.name.casefold() == researched_organization.strip().casefold():
            return organization
    for organization in organizations:
        if role_label in organization.role_labels:
            return organization
    return default


def _researched_memberships(
    researched: List[ResearchedPerson],
    organizations: List[KnownOrganization],
    taxonomy: Taxonomy,
) -> List[ExpectedMembership]:
    """Every role research names is expected: the form's role labels are a hint to research, not
    a filter on its answer. A label naming no role counts toward nothing, since progress is
    counted by role."""
    default = next(
        (organization for organization in organizations if organization.meta_is_default),
        organizations[0],
    )
    post_roles = [label for organization in organizations for label in organization.role_labels]
    expected = []
    for person in researched:
        parsed = parse_label_preferring(person.label, taxonomy, post_roles)
        if not parsed.role:
            continue
        designations = (
            [f"{parsed.division.designation} {parsed.division.value}"] if parsed.division else []
        )
        expected.append(
            ExpectedMembership(
                organization_id=_organization_for(
                    person.organization, parsed.role, organizations, default
                ).id,
                role_label=parsed.role,
                division=_first_division(designations),
                designations=parsed.other_designations,
            )
        )
    return expected


def _can_research() -> bool:
    """Whether a research provider is configured. Gemini is the only one."""
    return bool(get_env_vars().get("GOOGLE_GEMINI_TOKEN"))


async def _research_roster(
    context: PeopleCollectorContext, organizations: List[KnownOrganization], logger
) -> List[ResearchedPerson]:
    """Who is there, for a jurisdiction with no posts yet. The organizations' usual roles go in
    as a hint; the offices research names come back as the answer."""
    prompt = google_gemini_prompt.research_municipality_prompt(
        context.data.jurisdiction_ocdid, context.data.config.name or "", organizations
    )
    # Tool call + JSON output doesn't work at the same time for Google Gemini,
    # let's retry a couple times til it works.
    return await with_retry(logger, func=lambda: _request_roster(context, prompt))


async def _request_roster(
    context: PeopleCollectorContext, prompt: str
) -> List[ResearchedPerson]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(
        f"Researching with LLM for jurisdiction {context.data.jurisdiction_ocdid}"
    )

    response = await google_gemini_llm.run_prompt(
        context.pipeline_run_id,
        context.data.jurisdiction_ocdid,
        prompt,
        prompt_name="research_municipality",
    )

    if not response:
        raise ValueError("No response from LLM")
    people = response.get("people", [])

    return _as_researched_people(people)


def _as_researched_people(people: List[dict]) -> List[ResearchedPerson]:
    formatted_people = []
    for person in people:
        if not person.get("name"):
            continue
        formatted_people.append(ResearchedPerson.model_validate(person))
    return formatted_people


async def _source_urls(
    config, api_client: httpx.AsyncClient, logger, jurisdiction_ocdid: str
) -> List[str]:
    """Where to start crawling: a configured list wins, else the published roster's pages."""
    if config.source_urls:
        return config.source_urls
    return await civicpatch_api.get_roster_source_urls(api_client, logger, jurisdiction_ocdid)
