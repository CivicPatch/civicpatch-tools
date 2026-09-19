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
from runners.people_collector.schemas import (
    ExpectedMembership,
    PeopleCollectorContext,
    PipelineStatus,
    ResearchedPerson,
    ResearchMunicipalityStep,
)
from shared.schemas import KnownOrganization, Membership, Person, Post, RoleConfig
from shared.utils import divisions
from shared.utils.label_parser import parse_label
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
    logger.info(f"Step 1: {PipelineStatus.RESEARCH_MUNICIPALITY.value}")

    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    existing = await civicpatch_api.get_active_people(api_client, jurisdiction_ocdid)
    organizations = await civicpatch_api.get_organizations(api_client, jurisdiction_ocdid)
    posts = [post for organization in organizations for post in organization.posts]

    researched: List[ResearchedPerson] = []
    if posts:
        logger.info(f"research_municipality: {len(posts)} known posts, skipping research.")
    else:
        researched = await _research_roster(context, logger) if _can_research() else []

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
            or _researched_memberships(researched, organizations, taxonomy)
        ),
        # Whoever cp.org has published, else whoever research named. Separate from the offices
        # above: a jurisdiction can have posts and nobody accepted onto them yet.
        identities=_identities(existing, researched),
        source_urls=_source_urls(
            context.data.config, [Person(**person) for person in existing]
        ),
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
    labels_by_id = {role.id: role.label for role in (role_config.roles if role_config else [])}
    return [
        ExpectedMembership(
            organization_id=post.organization_id,
            role_label=labels_by_id[post.role_id],
            division=_division(post.division_ocdid, jurisdiction_ocdid),
            designations=_designations_held_on(post, held),
        )
        for post in posts
        if post.role_id != UNMATCHED_ROLE_ID
    ]


def _designations_held_on(post: Post, held: List[Membership]) -> List[str]:
    return list(
        dict.fromkeys(
            designation
            for membership in held
            if membership.post_id == post.id
            for designation in membership.designations
        )
    )


def _division(division_ocdid: str, jurisdiction_ocdid: str) -> Optional[str]:
    return _first_division(divisions.division_ocdid_to_designation(division_ocdid, jurisdiction_ocdid))


def _first_division(designations: List[str]) -> Optional[str]:
    found = divisions.filter_divisions(designations)
    return found[0] if found else None


def _researched_memberships(
    researched: List[ResearchedPerson],
    organizations: List[KnownOrganization],
    taxonomy: Taxonomy,
) -> List[ExpectedMembership]:
    """Research knows no organizations, so everyone it named belongs to the default one. A label
    naming no role counts toward nothing, since progress is counted by role."""
    default = next(
        (organization for organization in organizations if organization.meta_is_default),
        organizations[0],
    )
    expected = []
    for person in researched:
        parsed = parse_label(person.label, taxonomy)
        if not parsed.role:
            continue
        designations = (
            [f"{parsed.division.designation} {parsed.division.value}"] if parsed.division else []
        )
        expected.append(
            ExpectedMembership(
                organization_id=default.id,
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
    context: PeopleCollectorContext, logger
) -> List[ResearchedPerson]:
    """Who might be there, for a jurisdiction we have not published anybody from.

    Names alone — which offices exist is cp.org's answer, not the model's. Those offices go
    into the prompt though: naming them turns an open question into a roll call, and the
    scrape has posts to work from well before it has people, since posts derive at ingest.
    """
    prompt = google_gemini_prompt.research_municipality_prompt(
        context.data.jurisdiction_ocdid, context.data.config.name or ""
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


def _source_urls(config, people: List[Person]) -> List[str]:
    """Where to start crawling: a configured list wins, else the pages the published memberships
    were read from."""
    if config.source_urls:
        return config.source_urls
    return _membership_pages(people)


def _membership_pages(people: List[Person]) -> List[str]:
    """Every page each organization was found on, roster pages first.

    Ordered by how many people were read from a page, so a five-member council's directory comes
    before the five bios it links to. The bios stay: a page that listed one person last time is
    still where that person was, and dropping it is only correct if the directory really does
    cover everyone, which is the thing a scrape is running to find out.

    A page can belong to two organizations — a shared "elected officials" listing is where both
    the council and the mayor were read — so it is counted across organizations and seeded once.
    """
    people_by_url: Dict[str, set] = {}
    for person in people:
        for membership in person.memberships:
            for url in membership.source_urls:
                people_by_url.setdefault(url, set()).add(person.id)
    return sorted(people_by_url, key=lambda url: -len(people_by_url[url]))
