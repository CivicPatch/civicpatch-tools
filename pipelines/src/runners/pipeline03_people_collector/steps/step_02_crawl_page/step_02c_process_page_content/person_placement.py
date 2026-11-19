"""Which of ours each scraped person sits on. Rules first: the person's own role, then the words of the
organization label. What they leave open goes to Jev, and to the model when Jev is unsure, both shown the
page's headings; "none" leaves the record to ingest, which keeps it in the default organization."""

import asyncio
from typing import Dict, List, Sequence

from bs4 import BeautifulSoup
from pydantic import BaseModel

import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompts
from runners.pipeline03_people_collector.constants import JEV_CONFIDENCE_FLOOR, MATCH_MAX_OUTPUT_TOKENS
from runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02c_process_page_content.organization_match import (
    PlaceWords,
    match_by_words,
    match_response_schema,
    place_words,
    with_role_aliases,
)
from services.open_router import decisions
from services.open_router.prompts import NO_ORGANIZATION
from shared.schemas import KnownOrganization, SelectionMethod
from shared.utils.statuses import OrganizationPlacedBy
from shared.utils.label_parser import parse_label
from shared.utils.taxonomy import MEMBER_ROLE_ID, Taxonomy, lookup_key
from utils import log_utils

PROMPT_NAME = "person_organization"
JEV_PROMPT_NAME = "person_organization_jev"


class PageHeadings(BaseModel):
    title: str | None = None
    first_heading: str | None = None


class RulePlacement(BaseModel):
    # False when the rules cannot say and a model must; `name` None then, or for "no listed body".
    settled: bool
    name: str | None = None
    placed_by: OrganizationPlacedBy | None = None


class Placement(BaseModel):
    # None for "no listed body": ingest places the record in the default organization.
    name: str | None
    placed_by: OrganizationPlacedBy | None


_OPEN = RulePlacement(settled=False)
# Open with no listed body to ask about: ingest places it.
_UNPLACED = Placement(name=None, placed_by=None)


def page_headings(html: str | bytes) -> PageHeadings:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    heading = soup.find("h1")
    first_heading = heading.get_text(" ", strip=True) if heading else ""
    return PageHeadings(title=title or None, first_heading=first_heading or None)


def _is_position(role: str, taxonomy: Taxonomy) -> bool:
    return taxonomy.role_ids.get(role) == MEMBER_ROLE_ID or taxonomy.selection_methods.get(role) == SelectionMethod.ELECTED_BY_MEMBERS


def _held_roles(organization: KnownOrganization, taxonomy: Taxonomy) -> set[str]:
    held = (taxonomy.role_aliases.get(lookup_key(label)) for label in organization.role_labels)
    return {role for role in held if role is not None}


def _named(text: str, place: PlaceWords) -> str | None:
    match = match_by_words(text, place)
    return match.names[0] if len(match.names) == 1 and not match.uncertain else None


def _by_role(label: str, place: PlaceWords, taxonomy: Taxonomy) -> RulePlacement:
    """A seat on one listed body places there, by its role or by the label's own words naming it; officer
    roles and no seat place in the default ("Treasurer" under "Board of Trustees")."""
    roles = [role for role in parse_label(label, taxonomy).roles if not _is_position(role, taxonomy)]
    seats = {known.name for known in place.candidates for role in roles if role in _held_roles(known, taxonomy)}
    named = _named(label, place)
    if named:
        seats.add(named)
    if len(seats) == 1:
        return RulePlacement(settled=True, name=seats.pop(), placed_by=OrganizationPlacedBy.ROLE)
    if roles and not seats:
        default = place.defaults[0].name if place.defaults else None
        return RulePlacement(settled=True, name=default, placed_by=OrganizationPlacedBy.ROLE)
    return _OPEN


def placed_by_rules(organization_label: str | None, label: str, place: PlaceWords, taxonomy: Taxonomy) -> RulePlacement:
    by_role = _by_role(label, place, taxonomy)
    if by_role.settled:
        return by_role
    if organization_label:
        match = match_by_words(organization_label, place)
        if len(match.names) == 1 and not match.uncertain:
            return RulePlacement(settled=True, name=match.names[0], placed_by=OrganizationPlacedBy.HEADING)
    return _OPEN


async def _asked(
    person: tuple[str | None, str],
    choices: List[str],
    headings: PageHeadings,
    pipeline_run_id,
    jurisdiction_ocdid: str,
    place_name: str,
    source_url: str,
) -> Placement:
    organization_label, label = person
    state = {
        "place": place_name,
        "page_title": headings.title,
        "page_heading": headings.first_heading,
        "organization_label": organization_label,
        "person_label": label,
    }
    jev = await decisions.choose(
        pipeline_run_id,
        jurisdiction_ocdid,
        JEV_PROMPT_NAME,
        source_url,
        state,
        open_router_prompts.PERSON_ORGANIZATION_INSTRUCTIONS,
        open_router_prompts.person_organization_criteria(choices),
    )
    if (jev.confidence or 0) >= JEV_CONFIDENCE_FLOOR:
        return Placement(name=jev.choice if jev.choice in choices else None, placed_by=OrganizationPlacedBy.JEV)
    answer = await open_router_llm.run_prompt(
        pipeline_run_id,
        jurisdiction_ocdid,
        open_router_prompts.person_organization_prompt(),
        prompt_name=PROMPT_NAME,
        response_schema=match_response_schema(choices),
        content=open_router_prompts.person_organization_question(
            place_name, headings.title, headings.first_heading, organization_label, label, choices
        ),
        max_output_tokens=MATCH_MAX_OUTPUT_TOKENS,
        source_url=source_url,
    )
    picked = getattr(answer, "organization", NO_ORGANIZATION)
    log_utils.get_pipeline_run_logger(jurisdiction_ocdid).warning(
        f"Organization by the model, Jev unsure ({jev.confidence}): {label!r} under {organization_label!r} -> {picked}"
    )
    return Placement(name=picked if picked in choices else None, placed_by=OrganizationPlacedBy.LLM)


async def placed_names(
    people: Sequence[tuple[str | None, str]],
    organizations: List[KnownOrganization],
    taxonomy: Taxonomy,
    headings: PageHeadings,
    pipeline_run_id,
    jurisdiction_ocdid: str,
    place_name: str,
    source_url: str,
) -> List[Placement]:
    """Each (organization label, label)'s organization and what decided it; one ask per distinct open pair."""
    place = place_words(with_role_aliases(organizations, taxonomy), taxonomy, place_name)
    by_rules = [placed_by_rules(organization_label, label, place, taxonomy) for organization_label, label in people]
    choices = [known.name for known in place.candidates]
    # With no listed body to choose, there is nothing to ask: ingest places every open record.
    open_people = list(dict.fromkeys(person for person, placement in zip(people, by_rules) if not placement.settled)) if choices else []
    asked = await asyncio.gather(
        *[_asked(person, choices, headings, pipeline_run_id, jurisdiction_ocdid, place_name, source_url) for person in open_people]
    )
    answers: Dict[tuple[str | None, str], Placement] = dict(zip(open_people, asked))
    return [
        Placement(name=placement.name, placed_by=placement.placed_by) if placement.settled else answers.get(person, _UNPLACED)
        for person, placement in zip(people, by_rules)
    ]
