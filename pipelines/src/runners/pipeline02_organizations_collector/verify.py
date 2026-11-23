"""What VERIFY decides about each role from EXTRACT's answers: a post, citing every quote the law
supports it with; asked again; or no post. Pure: answers and cached pages in, outcomes out. A
quote is checked against the whole cached page it came from, not the sections EXTRACT read."""

from typing import List

from .role_asks import RoleAsk
from .schemas import Citation, FilledBy, RoleClaim, RoleOutcomes
from .sections import GoverningLawPage, page_kind
from shared.schemas import GoverningLaw, GoverningLawKind, GoverningLawPost, GoverningLawPostExtras, SelectionMethod, Source, SourceExtras
from shared.utils.citation import supporting_quote
from shared.utils.layered_config import GovernedBy, GoverningLawConfig

# A role with no quote yet is asked again until this many rounds have been asked.
MAX_ROUNDS = 3
CHARTER_GOVERNS = frozenset({GovernedBy.CHARTER, GovernedBy.CHARTER_ELSE_GENERAL_LAW})
# Enough of a quote in the run log to tell which clause an answer pointed at.
QUOTE_PREVIEW_CHARS = 120


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


def unanswered_asks(asks: List[RoleAsk], claims: List[RoleClaim]) -> List[RoleAsk]:
    answered = {claim.ask.role_id for claim in claims}
    return [ask for ask in asks if ask.role_id not in answered]


def unquoted_charter_urls(
    posts: List[GoverningLawPost],
    pages: List[GoverningLawPage],
    governing_law: GoverningLaw,
    governing_law_config: GoverningLawConfig | None,
    governing_bodies: List[str],
) -> List[str]:
    """A real charter sets up the body that governs, so one that governs and is quoted for no governing body's
    post is not the charter: a page that only quotes a clause of it (Estacada's city manager page) included."""
    if not _charter_governs(governing_law, governing_law_config):
        return []
    charter_pages = [page for page in pages if page_kind(page, governing_law, governing_law_config) == GoverningLawKind.CHARTER]
    charter_page_ids = {page.id for page in charter_pages}
    governing_posts = [post for post in posts if post.organization_id in governing_bodies]
    if any(source.extras.source_page_id in charter_page_ids for post in governing_posts for source in post.sources):
        return []
    return [page.source_url for page in charter_pages]


def _charter_governs(governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None) -> bool:
    """Not where the general law may hold every office (Vermont's towns): their charters can be partial."""
    if governing_law.kind != GoverningLawKind.CHARTER or governing_law_config is None or governing_law.classification is None:
        return False
    classification = governing_law_config.classifications.get(governing_law.classification)
    return classification is not None and classification.governed_by in CHARTER_GOVERNS


def citation(
    claim: RoleClaim, pages: List[GoverningLawPage], governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None
) -> Citation | None:
    """The claim's supporting quote and the page holding it; None when it says the office is not
    established or no page supports its quote."""
    answer = claim.answer
    if not answer.established:
        return None
    method = None if answer.filled_by == FilledBy.NOT_STATED else SelectionMethod(answer.filled_by.value)
    # A quote may establish the office without the words for how it is filled ("shall choose"): it is
    # still cited, without the method, and the role's default applies.
    for wanted in dict.fromkeys([method, None]):
        for page in pages:
            quote = supporting_quote(page.text, answer.quote, claim.ask.names, wanted)
            if quote is not None:
                return Citation(
                    quote=quote,
                    source_page_id=page.id,
                    source_url=page.source_url,
                    page_kind=page_kind(page, governing_law, governing_law_config),
                    selection_method=wanted,
                )
    return None


def role_summaries(claims: List[RoleClaim], outcomes: RoleOutcomes) -> List[str]:
    """One run-log line per role asked: how many answers found the office and how it is filled, what
    VERIFY made of it, and the first quote. The answers are not kept anywhere else."""
    posted = {post.role for post in outcomes.posts}
    re_asked = {ask.role_id for ask in outcomes.re_ask}
    return [_summary(ask, role_claims, posted, re_asked) for ask, role_claims in _by_role(claims)]


def _summary(ask: RoleAsk, claims: List[RoleClaim], posted: set[str], re_asked: set[str]) -> str:
    found = [claim.answer for claim in claims if claim.answer.established]
    methods = sorted({answer.filled_by.value for answer in found})
    quote = next((answer.quote for answer in found if answer.quote), "")
    if ask.role_id in posted:
        verdict = "posted"
    elif ask.role_id in re_asked:
        verdict = "asked again"
    else:
        verdict = "no post"
    method_text = f" ({', '.join(methods)})" if methods else ""
    quote_text = f", first quote {quote[:QUOTE_PREVIEW_CHARS]!r}" if quote else ""
    return f"{ask.organization_name} / {ask.role_label}: {len(found)} of {len(claims)} found it{method_text}, {verdict}{quote_text}"


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
