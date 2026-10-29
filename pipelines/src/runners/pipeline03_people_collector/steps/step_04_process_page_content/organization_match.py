"""Which of ours an organization label names: the organization as a page writes it over its
people. Words first: a label equal to a name, or inside exactly one organization's vocabulary
(its name and role labels), names that organization; one that several vocabularies cover
together names them all, and the person's own label picks among them; one sharing no word with
any names none; anything between is asked of the model, once per distinct label. Measured 2026-10-28: the words settle most, the
model errs only without the lookalike rule in its prompt."""

import asyncio
import re
from collections import Counter
from typing import Dict, Iterable, List, Literal, Sequence

from pydantic import BaseModel, create_model

import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompts
from runners.pipeline03_people_collector.constants import MATCH_MAX_OUTPUT_TOKENS
from services.open_router.prompts import NO_ORGANIZATION
from shared.schemas import KnownOrganization, PersonSourceRecord
from shared.utils.taxonomy import Taxonomy, lookup_key

# Grammar, which names no body anywhere. Words that do, but that several of a place's organizations
# share ("board", "town", "trustee"), are found from the place's own organizations instead.
_GRAMMAR_WORDS = {"of", "the", "and", "a", "an", "for", "to", "in", "on", "at", "by"}
# Words for a kind of body, never a particular one: "Committee Members" names none.
_BODY_KIND_WORDS = {"board", "committee", "commission", "office"}
_WORD = re.compile(r"[a-z]+")
# Words that name a position on any body, not the body: a label made only of them names none.
_POSITION_WORDS = {"chair", "chairman", "chairperson", "chairwoman", "vice", "member", "clerk", "secretary", "president", "co"}
# Words beside an office's name that say nothing about which body: a term, an election, contact.
_INCIDENTAL_WORDS = {"year", "term", "elected", "school", "information", "info", "contact", "current", "expire", "expires"}
# A page lists one person under several organizations; the model joins them with commas.
_LABEL_SEPARATOR = re.compile(r"[,;]")


class OrganizationLabelMatch(BaseModel):
    """What the words make of an organization label: no organization, one, or the several it names
    together ("Mayor & City Council"); `uncertain` when they cannot say and the model should."""

    names: List[str] = []
    uncertain: bool = False


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _tokens(text: str) -> List[str]:
    return [_singular(word) for word in _WORD.findall(text.lower()) if len(word) > 1]


def _terms(text: str) -> set[str]:
    return {token for token in _tokens(text) if token not in _GRAMMAR_WORDS}


def _own_terms(organization: KnownOrganization) -> set[str]:
    return _terms(organization.name).union(*[_terms(label) for label in organization.role_labels])


def shared_terms(organizations: List[KnownOrganization]) -> set[str]:
    """The words two or more of a place's organizations use: they cannot tell those apart."""
    counts = Counter(term for organization in organizations for term in _own_terms(organization))
    return {term for term, count in counts.items() if count > 1}


def words(text: str, shared: set[str]) -> set[str]:
    return _terms(text) - shared - _BODY_KIND_WORDS


def vocabulary(organization: KnownOrganization, shared: set[str]) -> set[str]:
    return _own_terms(organization) - shared - _BODY_KIND_WORDS


def _covered(written: set[str], known: set[str]) -> set[str]:
    """The written words a vocabulary accounts for, a stem counting ("commission" for "commissioner")."""
    return {word for word in written if word in known or any(term.startswith(word) for term in known if len(word) >= 5)}


def without_default(organizations: List[KnownOrganization]) -> List[KnownOrganization]:
    """Every organization a label may name. The default is our bucket for anyone unplaced;
    offering it made P4's duplicates."""
    return [organization for organization in organizations if not organization.meta_is_default]


def matched_organization_ids(records: List[PersonSourceRecord]) -> List[str]:
    return list(dict.fromkeys(record.organization_id for record in records if record.organization_id))


def with_role_aliases(organizations: List[KnownOrganization], taxonomy: Taxonomy) -> List[KnownOrganization]:
    """Each organization with the taxonomy aliases of its roles spelled from its own words
    ("Selectmen" extends "select"); a broad alias such as "Commissioner" is left out."""
    widened = []
    for organization in organizations:
        own = _own_terms(organization)
        roles = {taxonomy.role_aliases.get(lookup_key(label)) for label in organization.role_labels} - {None}
        extra = [
            alias
            for alias, canonical in taxonomy.role_aliases.items()
            if canonical in roles and _terms(alias) and all(_extends(word, own) for word in _terms(alias))
        ]
        widened.append(organization.model_copy(update={"role_labels": [*organization.role_labels, *extra]}))
    return widened


def _extends(word: str, own: set[str]) -> bool:
    return any(word.startswith(known) for known in own if len(known) >= 5)


def _contains(tokens: List[str], phrase: List[str]) -> bool:
    return bool(phrase) and any(tokens[i:i + len(phrase)] == phrase for i in range(len(tokens) - len(phrase) + 1))


def _named_by_role_label(text: str, candidates: List[KnownOrganization], shared: set[str]) -> List[str]:
    """The organizations one of whose own role labels the text contains whole, with nothing else
    but incidental words ("Moderator (Town & School)", "Board of Listers (Elected)"). A place or a
    second body among the rest ("Saxtons River Village Trustees") blocks it; so does a label of
    position words only ("Chair")."""
    tokens = text.split()
    written = words(text, shared)
    named = []
    for known in candidates:
        for label in known.role_labels:
            phrase = _tokens(label)
            if set(phrase) <= _POSITION_WORDS | _GRAMMAR_WORDS | shared or not _contains(tokens, phrase):
                continue
            if written - words(label, shared) <= _INCIDENTAL_WORDS:
                named.append(known.name)
                break
    return named


def _without_place(organization: str, place_name: str, organizations: List[KnownOrganization]) -> str:
    """The label without the place's own name, nor the kind of place its default names ("City Officers")."""
    defaults = [known.name for known in organizations if known.meta_is_default]
    place = set(_tokens(place_name)).union(*[set(_tokens(name)) for name in defaults])
    return " ".join(token for token in _tokens(organization) if token not in place)


def match_by_words(organization_label: str, place_name: str, organizations: List[KnownOrganization]) -> OrganizationLabelMatch:
    """The place's own name is dropped from the label ("Sutton Selectboard"); the default
    is never a candidate."""
    if "@" in organization_label:
        return OrganizationLabelMatch()
    candidates = without_default(organizations)
    shared = shared_terms(organizations)
    text = _without_place(organization_label, place_name, organizations)
    whole = [known.name for known in candidates if text == " ".join(_tokens(known.name))]
    if len(whole) == 1:
        return OrganizationLabelMatch(names=whole)
    written = words(text, shared)
    if not written or written <= _POSITION_WORDS:
        return OrganizationLabelMatch()
    by_role_label = _named_by_role_label(text, candidates, shared)
    if len(by_role_label) == 1:
        return OrganizationLabelMatch(names=by_role_label)
    if _named_by_role_label(text, [known for known in organizations if known.meta_is_default], shared):
        # An office of the default ("Trustee of Public Money"): no board, the person's own label places them.
        return OrganizationLabelMatch()
    covering = [known.name for known in candidates if _covered(written, vocabulary(known, shared)) == written]
    if len(covering) == 1:
        return OrganizationLabelMatch(names=covering)
    if covering:
        # It fits several of the law's organizations equally ("Trustees" in a town): the page does
        # not say which, so none, and the person's own label decides.
        return OrganizationLabelMatch()
    sharing = [known for known in candidates if _covered(written, vocabulary(known, shared))]
    if sharing and set().union(*[_covered(written, vocabulary(known, shared)) for known in sharing]) <= _POSITION_WORDS:
        # Only a position in common ("Paul Warden, Chair"): every board has one, so none.
        return OrganizationLabelMatch()
    if not covering and len(sharing) > 1 and _covered(written, set().union(*[vocabulary(known, shared) for known in sharing])) == written:
        return OrganizationLabelMatch(names=[known.name for known in sharing])
    return OrganizationLabelMatch(uncertain=bool(covering or sharing))


def match_response_schema(choices: List[str]) -> type[BaseModel]:
    """An enum of the choices, so the model cannot name an organization we do not have."""
    choice = Literal[tuple([*choices, NO_ORGANIZATION])]  # type: ignore[valid-type]
    return create_model("OrganizationMatch", organization=(choice, ...))


async def ask_organization(
    pipeline_run_id, jurisdiction_ocdid: str, place_name: str, organization: str, organizations: List[KnownOrganization]
) -> List[str]:
    choices = [known.name for known in without_default(organizations)]
    answer = await open_router_llm.run_prompt(
        pipeline_run_id,
        jurisdiction_ocdid,
        open_router_prompts.organization_match_prompt(),
        prompt_name="organization_match",
        response_schema=match_response_schema(choices),
        content=open_router_prompts.organization_match_question(place_name, organization, choices),
        max_output_tokens=MATCH_MAX_OUTPUT_TOKENS,
    )
    picked = getattr(answer, "organization", NO_ORGANIZATION)
    return [] if picked == NO_ORGANIZATION else [picked]


def label_parts(organization_label: str) -> List[str]:
    return [part.strip() for part in _LABEL_SEPARATOR.split(organization_label) if part.strip()]


async def resolve_organizations(
    organization_labels: Iterable[str | None], pipeline_run_id, jurisdiction_ocdid: str, place_name: str, organizations: List[KnownOrganization]
) -> Dict[str, List[str]]:
    """Each distinct organization label to the organization names it means, empty for none; a
    comma-joined label means the first of its parts that names any. The model is asked only
    for the parts the words leave uncertain, once each."""
    parts = {part for label in organization_labels if label for part in label_parts(label)}
    by_words = {part: match_by_words(part, place_name, organizations) for part in parts}
    uncertain = [part for part, match in by_words.items() if match.uncertain]
    asked = await asyncio.gather(
        *[ask_organization(pipeline_run_id, jurisdiction_ocdid, place_name, part, organizations) for part in uncertain]
    )
    per_part = {part: match.names for part, match in by_words.items()}
    per_part.update(zip(uncertain, asked))
    resolved: Dict[str, List[str]] = {}
    for label in organization_labels:
        if label:
            resolved[label] = next((per_part[part] for part in label_parts(label) if per_part[part]), [])
    return resolved


async def placed_names(
    people: Sequence[tuple[str | None, str]],
    organizations: List[KnownOrganization],
    taxonomy: Taxonomy,
    pipeline_run_id,
    jurisdiction_ocdid: str,
    place_name: str,
) -> List[str | None]:
    """Each person's organization by the (organization label, label) they were listed under:
    today's taxonomy aliases widen the vocabulary, the words decide, the model is asked once per
    distinct label they leave open, and the person's own label picks among several bodies."""
    matching = with_role_aliases(organizations, taxonomy)
    resolved = await resolve_organizations(
        [organization_label for organization_label, _ in people], pipeline_run_id, jurisdiction_ocdid, place_name, matching
    )
    return [placed_name(organization_label, label, resolved, matching) for organization_label, label in people]


def organization_by_label(label: str | None, organizations: List[KnownOrganization]) -> str | None:
    """The one organization whose vocabulary shares the most of the label's words ("Council
    Member District 1" shares "council"), else None."""
    common = shared_terms(organizations)
    written = words(label or "", common) - _POSITION_WORDS
    overlap = {known.name: len(written & vocabulary(known, common)) for known in without_default(organizations)}
    best = max(overlap.values(), default=0)
    winners = [name for name, count in overlap.items() if count == best]
    return winners[0] if best and len(winners) == 1 else None


def placed_name(organization_label: str | None, label: str | None, resolved: Dict[str, List[str]], organizations: List[KnownOrganization]) -> str | None:
    """Where a record goes by its organization label; among several bodies it names, by its own label."""
    names = resolved.get(organization_label or "", [])
    if len(names) == 1:
        return names[0]
    if len(names) > 1:
        named = [known for known in organizations if known.name in names]
        return organization_by_label(label, named)
    return None


def organization_id_by_name(name: str | None, organizations: List[KnownOrganization]) -> str | None:
    """None for no name: ingest places the record by its label."""
    ids_by_name = {known.name: known.id for known in organizations}
    return ids_by_name.get(name) if name else None
