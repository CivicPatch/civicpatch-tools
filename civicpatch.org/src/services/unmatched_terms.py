"""The triage list, worked out on request.

Each label's parse is remembered until the roles change, so a page view parses only wordings it
has not seen before. Adding an alias changes the roles, which forgets every parse.
"""

import hashlib
from collections.abc import Callable

from shared.schemas import Role, RoleConfig
from shared.utils.label_parser import parse_label
from shared.utils.taxonomy import Taxonomy, build_taxonomy

from core.unmatched_terms import TriageTerm, triage_terms
from database.memberships import open_membership_labels
from database.roles import get_roles

# One entry, for the roles as they stand: parses of labels under any other roles are stale.
_PARSES: dict[str, dict[str, tuple[str, ...]]] = {}


async def unmatched_terms_page(limit: int, offset: int) -> tuple[int, list[TriageTerm]]:
    """How many terms there are, and one page of them."""
    roles = await get_roles()
    unmatched_of = _remembering(_fingerprint(roles), build_taxonomy(RoleConfig(roles=roles)))
    terms = triage_terms(await open_membership_labels(), unmatched_of)
    return len(terms), terms[offset : offset + limit]


def _fingerprint(roles: list[Role]) -> str:
    digest = hashlib.sha256()
    for role in roles:
        digest.update(role.model_dump_json().encode())
    return digest.hexdigest()


def _remembering(fingerprint: str, taxonomy: Taxonomy) -> Callable[[str], tuple[str, ...]]:
    if fingerprint not in _PARSES:
        _PARSES.clear()
        _PARSES[fingerprint] = {}
    known = _PARSES[fingerprint]

    def unmatched_of(label: str) -> tuple[str, ...]:
        if label not in known:
            known[label] = _unmatched(label, taxonomy)
        return known[label]

    return unmatched_of


def _unmatched(label: str, taxonomy: Taxonomy) -> tuple[str, ...]:
    """What the label said that nothing matched. None when it names a role: the fold's rule, since
    words beside a known role are that role's qualifiers, not a gap in the taxonomy."""
    parsed = parse_label(label, taxonomy)
    return () if parsed.role else tuple(dict.fromkeys(parsed.unmatched))
