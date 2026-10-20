"""What VERIFY decides about each role from EXTRACT's answers: verified, not established, in
conflict, asked again, or left unverified. Pure: answers and cached pages in, outcomes out. A
quote is checked against the whole cached page it came from, not the sections EXTRACT read."""

from typing import List

from runners.organizations_collector.role_asks import RoleAsk
from runners.organizations_collector.schemas import FilledBy, RoleClaim, RoleOutcomes, VerifiedRole
from runners.organizations_collector.sections import GoverningLawPage, page_kind
from shared.schemas import GoverningLaw, GoverningLawKind, SelectionMethod
from shared.utils.citation import supporting_quote
from shared.utils.layered_config import GoverningLawConfig

# A role with no verified answer is asked again until this many rounds have been asked.
MAX_ROUNDS = 3


def role_outcomes(
    claims: List[RoleClaim],
    pages: List[GoverningLawPage],
    governing_law: GoverningLaw,
    governing_law_config: GoverningLawConfig | None,
    asks_per_question: int,
) -> RoleOutcomes:
    verified: List[VerifiedRole] = []
    not_established: List[RoleAsk] = []
    conflicted: List[RoleAsk] = []
    re_ask: List[RoleAsk] = []
    unverified: List[RoleAsk] = []
    for ask, role_claims in _by_role(claims):
        passed = _verified_claims(role_claims, pages, governing_law, governing_law_config)
        chosen = _agreed(passed)
        if chosen is not None:
            verified.append(chosen)
        elif passed:
            conflicted.append(ask)
        elif all(not claim.answer.established for claim in role_claims):
            not_established.append(ask)
        elif len(role_claims) // asks_per_question < MAX_ROUNDS:
            re_ask.append(ask)
        else:
            unverified.append(ask)
    return RoleOutcomes(
        verified=verified, not_established=not_established, conflicted=conflicted, re_ask=re_ask, unverified=unverified
    )


def verified_claim(
    claim: RoleClaim, pages: List[GoverningLawPage], governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None
) -> VerifiedRole | None:
    """The claim with its supporting quote and the page holding it; None when it says the office
    is not established or no page supports its quote."""
    answer = claim.answer
    if not answer.established:
        return None
    method = None if answer.filled_by == FilledBy.NOT_STATED else SelectionMethod(answer.filled_by.value)
    for page in pages:
        quote = supporting_quote(page.text, answer.quote, claim.ask.names, method)
        if quote is not None:
            return VerifiedRole(
                ask=claim.ask,
                label=answer.label,
                selection_method=method,
                maximum_memberships=answer.maximum_memberships,
                quote=quote,
                source_page_id=page.id,
                source_url=page.source_url,
                page_kind=page_kind(page, governing_law, governing_law_config),
            )
    return None


def _by_role(claims: List[RoleClaim]) -> List[tuple[RoleAsk, List[RoleClaim]]]:
    grouped: dict[str, tuple[RoleAsk, List[RoleClaim]]] = {}
    for claim in claims:
        grouped.setdefault(claim.ask.role_id, (claim.ask, []))[1].append(claim)
    return list(grouped.values())


def _verified_claims(
    claims: List[RoleClaim], pages: List[GoverningLawPage], governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None
) -> List[VerifiedRole]:
    verified: List[VerifiedRole] = []
    for claim in claims:
        found = verified_claim(claim, pages, governing_law, governing_law_config)
        if found is not None:
            verified.append(found)
    return verified


def _agreed(verified: List[VerifiedRole]) -> VerifiedRole | None:
    """One answer for the role: a stated method over "not stated", and where verified answers
    name two methods, the charter's; the charter's page cited when it has one. None when there is
    no answer, or the methods differ even in the charter."""
    stated = [role for role in verified if role.selection_method is not None]
    if len({role.selection_method for role in stated}) > 1:
        stated = [role for role in stated if role.page_kind == GoverningLawKind.CHARTER]
        if len({role.selection_method for role in stated}) != 1:
            return None
    pool = stated or verified
    if not pool:
        return None
    return sorted(pool, key=lambda role: role.page_kind != GoverningLawKind.CHARTER)[0]
