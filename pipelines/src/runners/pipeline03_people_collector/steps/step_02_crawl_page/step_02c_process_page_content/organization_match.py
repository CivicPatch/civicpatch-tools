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
from shared.schemas import KnownOrganization, PersonSourceRecord, SelectionMethod
from shared.utils.taxonomy import MEMBER_ROLE_ID, Taxonomy, lookup_key

# Grammar, which names no body anywhere. Words that do, but that several of a place's organizations
# share ("board", "town", "trustee"), are found from the place's own organizations instead.
_GRAMMAR_WORDS = {"of", "the", "and", "a", "an", "for", "to", "in", "on", "at", "by"}
# Words for a kind of body, never a particular one: "Committee Members" names none.
_BODY_KIND_WORDS = {"board", "committee", "commission", "office"}
_WORD = re.compile(r"[a-z0-9]+")
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
    """Words, singular; a number or ordinal ("3", "1st") is a seat's, never a body's."""
    return [_singular(word) for word in _WORD.findall(text.lower()) if len(word) > 1 and not any(c.isdigit() for c in word)]


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


def _role_terms(taxonomy: Taxonomy, canonicals: set[str]) -> set[str]:
    return set().union(*[_terms(alias) for alias, canonical in taxonomy.role_aliases.items() if canonical in canonicals])


def position_words(taxonomy: Taxonomy, organizations: List[KnownOrganization]) -> set[str]:
    """Words for a position any body can hold: the roles its members fill (Chair, Vice President,
    Mayor Pro Tempore) and Member, minus any word another role's own label uses ("mayor") or one of
    the place's organizations is named by ("council")."""
    by_members = {role for role, method in taxonomy.selection_methods.items() if method == SelectionMethod.ELECTED_BY_MEMBERS}
    member = {role for role, role_id in taxonomy.role_ids.items() if role_id == MEMBER_ROLE_ID}
    others = set(taxonomy.selection_methods) - by_members - member
    blocked = set().union(*[_terms(role) for role in others], *[_terms(known.name) for known in organizations])
    return (_role_terms(taxonomy, by_members) | set().union(*[_terms(role) for role in member])) - blocked


def role_words(taxonomy: Taxonomy, organizations: List[KnownOrganization], shared: set[str]) -> set[str]:
    """Words naming any role in the taxonomy that are none of the candidates' own: they may stand
    beside a body's name ("Select Board Clerk") without changing which body it is."""
    every_role = set(taxonomy.role_aliases.values())
    own = set().union(*[vocabulary(known, shared) for known in without_default(organizations)])
    return (_role_terms(taxonomy, every_role) | set().union(*[_terms(role) for role in every_role])) - own


def designation_words(taxonomy: Taxonomy, organizations: List[KnownOrganization]) -> set[str]:
    """Words that say which seat, not which body ("District", "Ward", "At Large"): the taxonomy's
    designations and their one-word aliases, minus any word the place's organizations use."""
    canonical = set(taxonomy.designation_aliases.values())
    one_word = {alias for alias in taxonomy.designation_aliases if " " not in alias.strip()}
    found = set().union(*[_terms(term.replace("-", " ")) for term in canonical | one_word])
    return found - set().union(*[_own_terms(known) for known in organizations])


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


class PlaceWords(BaseModel):
    """What a place's organizations and the taxonomy say about words, worked out once per place."""

    candidates: List[KnownOrganization]
    defaults: List[KnownOrganization]
    # Each candidate's own words, those several organizations share removed.
    vocabularies: Dict[str, set[str]]
    shared: set[str]
    # The place's own name and the kind of place its default names ("City Officers").
    place: set[str]
    # Words for a position any body can hold ("chair", "vice", "member").
    positions: set[str]
    # Words of a role none of the candidates owns, which may stand beside a body's name ("clerk").
    roles_beside: set[str]
    # Words that say which seat, not which body ("district", "ward").
    seats: set[str]


def place_words(organizations: List[KnownOrganization], taxonomy: Taxonomy, place_name: str) -> PlaceWords:
    shared = shared_terms(organizations)
    candidates = without_default(organizations)
    defaults = [known for known in organizations if known.meta_is_default]
    return PlaceWords(
        candidates=candidates,
        defaults=defaults,
        vocabularies={known.name: vocabulary(known, shared) for known in candidates},
        shared=shared,
        place=set(_tokens(place_name)).union(*[set(_tokens(known.name)) for known in defaults]),
        positions=position_words(taxonomy, organizations),
        roles_beside=role_words(taxonomy, organizations, shared),
        seats=designation_words(taxonomy, organizations),
    )


class LabelWords(BaseModel):
    """One organization label read against a place."""

    raw: str
    # The label's words in order, the place's own name dropped ("Sutton Selectboard" -> "selectboard").
    text: str
    # Its words that can say which body: shared, grammar, body-kind and seat words removed.
    written: set[str]
    # Those words without roles none of the candidates owns ("Select Board Clerk" -> {"select"}).
    body: set[str]


def label_words(organization_label: str, place: PlaceWords) -> LabelWords:
    text = " ".join(token for token in _tokens(organization_label) if token not in place.place)
    written = words(text, place.shared) - place.seats
    return LabelWords(raw=organization_label, text=text, written=written, body=written - place.roles_beside)


def _named_by_role_label(text: str, organizations: List[KnownOrganization], place: PlaceWords) -> List[str]:
    """The organizations one of whose own role labels the text contains whole, with nothing else
    but incidental words or roles beside it ("Moderator (Town & School)", "Board of Listers
    (Elected)"). A place or a second body among the rest ("Saxtons River Village Trustees") blocks
    it; so does a label of position words only ("Chair")."""
    tokens = text.split()
    written = words(text, place.shared)
    named = []
    for known in organizations:
        for role_label in known.role_labels:
            phrase = _tokens(role_label)
            if set(phrase) <= place.positions | _GRAMMAR_WORDS | place.shared or not _contains(tokens, phrase):
                continue
            if written - words(role_label, place.shared) <= _INCIDENTAL_WORDS | place.roles_beside:
                named.append(known.name)
                break
    return named


def _covering(label: LabelWords, place: PlaceWords) -> List[str]:
    return [name for name, known in place.vocabularies.items() if _covered(label.body, known) == label.body]


def _sharing(label: LabelWords, place: PlaceWords) -> List[str]:
    return [name for name, known in place.vocabularies.items() if _covered(label.body, known)]


_NONE = OrganizationLabelMatch()


def _an_email_names_none(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"selectboard@townoforwellvt.org" is a link, not a heading."""
    return _NONE if "@" in label.raw else None


def _a_whole_name_names_it(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Township Board" is the Board, though "board" alone says nothing."""
    whole = [known.name for known in place.candidates if label.text == " ".join(_tokens(known.name))]
    return OrganizationLabelMatch(names=whole) if len(whole) == 1 else None


def _positions_alone_name_none(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Vice Chair": every board has one."""
    return _NONE if not label.written or label.written <= place.positions else None


def _one_role_label_names_it(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Moderator (Town & School)" names the one organization with a Moderator."""
    named = _named_by_role_label(label.text, place.candidates, place)
    return OrganizationLabelMatch(names=named) if len(named) == 1 else None


def _a_default_office_names_none(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Trustee of Public Money" is an office of the default, not a board: the person's own label places them."""
    return _NONE if _named_by_role_label(label.text, place.defaults, place) else None


def _roles_alone_name_none(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Town Clerk": a role, and nothing that names a body."""
    return _NONE if not label.body else None


def _one_vocabulary_names_it(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Lister Board" is inside the Board of Listers' words alone."""
    covering = _covering(label, place)
    return OrganizationLabelMatch(names=covering) if len(covering) == 1 else None


def _several_vocabularies_name_none(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Trustees" in a town fits two of the law's organizations: the page does not say which."""
    return _NONE if len(_covering(label, place)) > 1 else None


def _a_shared_position_names_none(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Paul Warden, Chair": the only word in common is a position every board has."""
    sharing = _sharing(label, place)
    covered = set().union(*[_covered(label.body, place.vocabularies[name]) for name in sharing])
    return _NONE if sharing and covered <= place.positions else None


def _several_bodies_together(label: LabelWords, place: PlaceWords) -> OrganizationLabelMatch | None:
    """"Mayor & City Council" names both; the person's own label picks between them."""
    sharing = _sharing(label, place)
    together = set().union(*[place.vocabularies[name] for name in sharing])
    if len(sharing) > 1 and _covered(label.body, together) == label.body:
        return OrganizationLabelMatch(names=sharing)
    return None


# In order: the first that decides wins.
_RULES = [
    _an_email_names_none,
    _a_whole_name_names_it,
    _positions_alone_name_none,
    _one_role_label_names_it,
    _a_default_office_names_none,
    _roles_alone_name_none,
    _one_vocabulary_names_it,
    _several_vocabularies_name_none,
    _a_shared_position_names_none,
    _several_bodies_together,
]


def match_by_words(organization_label: str, place: PlaceWords) -> OrganizationLabelMatch:
    """The first rule that decides; when none does, uncertain if any organization shares a word."""
    label = label_words(organization_label, place)
    for rule in _RULES:
        match = rule(label, place)
        if match is not None:
            return match
    return OrganizationLabelMatch(uncertain=bool(_sharing(label, place)))


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
    organization_labels: Iterable[str | None],
    pipeline_run_id,
    jurisdiction_ocdid: str,
    place_name: str,
    place: PlaceWords,
) -> Dict[str, List[str]]:
    """Each distinct organization label to the organization names it means, empty for none; a
    comma-joined label means the first of its parts that names any. The model is asked only
    for the parts the words leave uncertain, once each."""
    parts = {part for label in organization_labels if label for part in label_parts(label)}
    by_words = {part: match_by_words(part, place) for part in parts}
    uncertain = [part for part, match in by_words.items() if match.uncertain]
    asked = await asyncio.gather(
        *[ask_organization(pipeline_run_id, jurisdiction_ocdid, place_name, part, place.candidates) for part in uncertain]
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
    place = place_words(with_role_aliases(organizations, taxonomy), taxonomy, place_name)
    resolved = await resolve_organizations(
        [organization_label for organization_label, _ in people], pipeline_run_id, jurisdiction_ocdid, place_name, place
    )
    return [placed_name(organization_label, label, resolved, place, taxonomy) for organization_label, label in people]


def organization_by_label(label: str | None, organizations: List[KnownOrganization], taxonomy: Taxonomy) -> str | None:
    """The one organization whose vocabulary shares the most of the label's words ("Council
    Member District 1" shares "council"), else None."""
    common = shared_terms(organizations)
    written = words(label or "", common) - position_words(taxonomy, organizations)
    overlap = {known.name: len(written & vocabulary(known, common)) for known in without_default(organizations)}
    best = max(overlap.values(), default=0)
    winners = [name for name, count in overlap.items() if count == best]
    return winners[0] if best and len(winners) == 1 else None


def placed_name(
    organization_label: str | None,
    label: str | None,
    resolved: Dict[str, List[str]],
    place: PlaceWords,
    taxonomy: Taxonomy,
) -> str | None:
    """Where a record goes by its organization label; among several bodies it names, by its own
    label; and when it names none, by its own label read the same way ("Library Trustee")."""
    names = resolved.get(organization_label or "", [])
    if len(names) == 1:
        return names[0]
    if len(names) > 1:
        named = [known for known in place.candidates if known.name in names]
        return organization_by_label(label, named, taxonomy)
    by_own_label = match_by_words(label or "", place)
    return by_own_label.names[0] if len(by_own_label.names) == 1 else None


def organization_id_by_name(name: str | None, organizations: List[KnownOrganization]) -> str | None:
    """None for no name: ingest places the record by its label."""
    ids_by_name = {known.name: known.id for known in organizations}
    return ids_by_name.get(name) if name else None
