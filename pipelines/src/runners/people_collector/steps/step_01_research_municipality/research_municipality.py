"""Step 1 — what we already know about this jurisdiction, before looking at any page.

Three things steer the rest of the run: which names are one person (`identities`), which
offices to look for (`known_roles`), and which divisions they sit in (`target_divisions`).

Roles and divisions come off cp.org's `posts`, which is where they are decided. Research is
the cold-start path only, for a jurisdiction with no posts to read them from.
"""

from typing import Dict, List

import httpx
import services.civicpatch_api as civicpatch_api
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
from pipelines_environment import get_env_vars
from runners.people_collector.schemas import (
    PeopleCollectorContext,
    PipelineStatus,
    ResearchedPerson,
    ResearchMunicipalityStep,
)
from shared.schemas import Person, RoleConfig
from shared.utils import divisions
from shared.utils.label_parser import parse_label
from shared.utils.taxonomy import build_taxonomy
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
    posts = await civicpatch_api.get_posts(api_client, jurisdiction_ocdid)

    researched: List[ResearchedPerson] = []
    if posts:
        logger.info(f"research_municipality: {len(posts)} known posts, skipping research.")
        known_roles = _roles_from_posts(posts, context.data.role_config)
        target_divisions = _divisions_from_posts(posts, jurisdiction_ocdid)
        expected_count = len(existing) or _seat_count(posts)
        origin_source = "existing"
    else:
        researched = await _research_roster(context, logger) if _can_research() else []
        known_roles, target_divisions = _parts_from_research(
            researched, context.data.role_config
        )
        expected_count = len(researched)
        origin_source = "google_gemini" if researched else "none"

    return ResearchMunicipalityStep(
        expected_count=expected_count,
        researched=researched,
        target_divisions=target_divisions,
        known_roles=known_roles,
        # Whoever cp.org has published, else whoever research named. Separate from the offices
        # above: a jurisdiction can have posts and nobody accepted onto them yet.
        identities=_identities(existing, researched),
        source_urls=_source_urls(
            context.data.config, [Person(**person) for person in existing]
        ),
        origin_source=origin_source,
    )


def _identities(existing: List[dict], researched: List[ResearchedPerson]) -> Dict[str, List[str]]:
    if existing:
        return person_list_to_identities([Person(**person) for person in existing])
    return {person.name: [] for person in researched}


def _parts_from_research(
    researched: List[ResearchedPerson], role_config: RoleConfig | None
) -> tuple[List[str], List[str]]:
    """The offices research named, split into the parts a scrape steers by.

    The same `parse_label` cp.org runs at ingest, so a first scrape and every later one agree
    about what a label means. The only place the pipeline parses anything.
    """
    taxonomy = build_taxonomy(role_config)
    parsed = [parse_label(person.label, taxonomy) for person in researched if person.label]
    roles = [label.role for label in parsed if label.role]
    designations = [
        f"{label.division.designation} {label.division.value}"
        for label in parsed
        if label.division
    ]
    return list(dict.fromkeys(roles)), divisions.filter_divisions(designations)


def _seat_count(posts: List[dict]) -> int:
    """How many people the known posts have room for, headcount included: a five-seat
    at-large council is one post and five officials to find."""
    return sum(post.get("_headcount", 1) for post in posts)


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


def _divisions_from_posts(posts: List[dict], jurisdiction_ocdid: str) -> List[str]:
    """The divisions this jurisdiction's posts sit in, as the designations a label would name.

    A post covering the whole jurisdiction yields nothing — there is no ward to go looking for.
    """
    designations = []
    for post in posts:
        designations.extend(
            divisions.division_ocdid_to_designation(
                post.get("division_ocdid"), jurisdiction_ocdid
            )
        )
    return divisions.filter_divisions(designations)


def _roles_from_posts(posts: List[dict], role_config: RoleConfig | None) -> List[str]:
    """The offices this jurisdiction is known to have, by their taxonomy label.

    A lookup, not a resolution: the post already carries the decided `role_id`, so this only
    renders it. Order-preserving and deduplicated, because it becomes prompt keywords.
    """
    labels_by_id: Dict[str, str] = {
        role.id: role.label for role in (role_config.roles if role_config else [])
    }
    named = [labels_by_id[post["role_id"]] for post in posts if post["role_id"] in labels_by_id]
    return list(dict.fromkeys(named))


async def _request_roster(
    context: PeopleCollectorContext, prompt: str
) -> List[ResearchedPerson]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(
        f"Researching with LLM for jurisdiction {context.data.jurisdiction_ocdid}"
    )

    response = await google_gemini_llm.run_prompt(
        context.changeset_id,
        context.data.jurisdiction_ocdid,
        prompt,
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
    if config.source_urls:
        return config.source_urls
    url_counts = {}
    for person in people:
        for url in getattr(person, "source_urls", None) or []:
            url_counts[url] = url_counts.get(url, 0) + 1
    return [url for url, count in url_counts.items() if count > 1]
