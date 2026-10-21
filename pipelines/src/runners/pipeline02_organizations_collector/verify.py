"""What VERIFY decides about each role from EXTRACT's answers: a post, citing every quote the law
supports it with; asked again; or no post. Pure: answers and cached pages in, outcomes out. A
quote is checked against the whole cached page it came from, not the sections EXTRACT read."""

from typing import List

from .role_asks import RoleAsk
from .schemas import Citation, FilledBy, RoleClaim, RoleOutcomes
from .sections import GoverningLawPage, page_kind
from shared.schemas import GoverningLaw, GoverningLawKind, GoverningLawPost, GoverningLawPostExtras, SelectionMethod, Source, SourceExtras
from shared.utils.citation import supporting_quote
from shared.utils.layered_config import GoverningLawConfig

# A role with no quote yet is asked again until this many rounds have been asked.
MAX_ROUNDS = 3


def role_outcomes(
    claims: List[RoleClaim],
    pages: List[GoverningLawPage],
    governing_law: GoverningLaw,
    governing_law_config: GoverningLawConfig | None,
    asks_per_question: int,
) -> RoleOutcomes:
    posts: List[GoverningLawPost] = []
    re_ask: List[RoleAsk] = []
    for ask, role_claims in _by_role(claims):
        cited = _cited_claims(role_claims, pages, governing_law, governing_law_config)
        if cited:
            posts.append(_post(ask, cited))
            continue
        some_answer_found_the_office = any(claim.answer.established for claim in role_claims)
        if some_answer_found_the_office and len(role_claims) // asks_per_question < MAX_ROUNDS:
            re_ask.append(ask)
    return RoleOutcomes(posts=posts, re_ask=re_ask)


def citation(
    claim: RoleClaim, pages: List[GoverningLawPage], governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None
) -> Citation | None:
    """The claim's supporting quote and the page holding it; None when it says the office is not
    established or no page supports its quote."""
    answer = claim.answer
    if not answer.established:
        return None
    method = None if answer.filled_by == FilledBy.NOT_STATED else SelectionMethod(answer.filled_by.value)
    for page in pages:
        quote = supporting_quote(page.text, answer.quote, claim.ask.names, method)
        if quote is not None:
            return Citation(
                quote=quote,
                source_page_id=page.id,
                source_url=page.source_url,
                page_kind=page_kind(page, governing_law, governing_law_config),
                selection_method=method,
            )
    return None


def _by_role(claims: List[RoleClaim]) -> List[tuple[RoleAsk, List[RoleClaim]]]:
    grouped: dict[str, tuple[RoleAsk, List[RoleClaim]]] = {}
    for claim in claims:
        grouped.setdefault(claim.ask.role_id, (claim.ask, []))[1].append(claim)
    return list(grouped.values())


def _cited_claims(
    claims: List[RoleClaim], pages: List[GoverningLawPage], governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None
) -> List[tuple[RoleClaim, Citation]]:
    cited: List[tuple[RoleClaim, Citation]] = []
    for claim in claims:
        found = citation(claim, pages, governing_law, governing_law_config)
        if found is not None:
            cited.append((claim, found))
    return cited


def _post(ask: RoleAsk, cited: List[tuple[RoleClaim, Citation]]) -> GoverningLawPost:
    """Every distinct quote, the charter's first; the label and count from the first answer that
    states them."""
    citations: List[Citation] = []
    for _, found in sorted(cited, key=lambda pair: pair[1].page_kind != GoverningLawKind.CHARTER):
        if all(found.quote.text != kept.quote.text or found.selection_method != kept.selection_method for kept in citations):
            citations.append(found)
    answers = [claim.answer for claim, _ in cited]
    return GoverningLawPost(
        role=ask.role_id,
        label=next((answer.label for answer in answers if answer.label), ask.role_label),
        organization_id=ask.organization_name,
        maximum_memberships=next((answer.maximum_memberships for answer in answers if answer.maximum_memberships), None),
        sources=[_source(found) for found in citations],
        extras=GoverningLawPostExtras(selection_method=_method(citations)),
    )


def _source(found: Citation) -> Source:
    return Source(
        url=found.source_url,
        note=found.quote.text,
        extras=SourceExtras(source_page_id=found.source_page_id, matched_in=found.quote.scope),
    )


def _method(citations: List[Citation]) -> SelectionMethod | None:
    """The one method the quotes state; where they state two, the charter's if it states one;
    else None, and the role's default applies."""
    for pool in (citations, [found for found in citations if found.page_kind == GoverningLawKind.CHARTER]):
        stated = {found.selection_method for found in pool if found.selection_method is not None}
        if len(stated) == 1:
            return stated.pop()
    return None
