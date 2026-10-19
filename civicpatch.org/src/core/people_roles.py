"""Which office a person's labels imply: the role that won, the division, what matched nothing.

`shared.utils.label_parser` reads one label; this decides across every label one person was
seen under, which is the decision a single label cannot make.

Pure — labels and a taxonomy in, structure out — and never stored. A parser fix therefore
changes what history means without any row needing to be rewritten, which is why
`source_records` keeps labels verbatim and nothing derived.

The decision, not its rendering: `projection.posts` turns this into posts, and
`membership_label` turns it into words.
"""

from pydantic import BaseModel

from shared.schemas import SelectionMethod
from shared.utils.label_parser import ParsedLabel, division_ocdid, parse_label
from shared.utils.taxonomy import Taxonomy


class LabelPart(BaseModel):
    """One raw label beside its parse. Paired, not flattened — which designation came off
    which label is what a person named twice on one page needs."""

    label: str
    parsed: ParsedLabel


class DerivedRoles(BaseModel):
    """What one person's labels imply.

    `role` + `division_ocdid` identify the post; `other_designations`, `unmatched` and the
    losing `roles` describe the person in it.
    """

    labels: list[str] = []
    parts: list[LabelPart] = []
    role: str | None = None
    roles: list[str] = []
    division_ocdid: str = ""
    other_designations: list[str] = []
    unmatched: list[str] = []


def derive_roles(
    labels: list[str], jurisdiction_ocdid: str, taxonomy: Taxonomy
) -> DerivedRoles:
    """The derivation across every label one person was seen under. Never stored — pure, so
    the answer is recomputed rather than kept."""
    parsed = [parse_label(label, taxonomy) for label in labels]
    roles = _unique([role for p in parsed for role in p.roles])
    return DerivedRoles(
        labels=labels,
        parts=[
            LabelPart(label=label, parsed=part)
            for label, part in zip(labels, parsed)
        ],
        role=_winning_role(roles, taxonomy),
        roles=roles,
        division_ocdid=_division_ocdid(parsed, jurisdiction_ocdid),
        other_designations=_unique([d for p in parsed for d in p.other_designations]),
        unmatched=_unique([term for p in parsed for term in p.unmatched]),
    )


def is_elected_by_voters(role: str, taxonomy: Taxonomy) -> bool:
    return _selection_method(role, taxonomy) == SelectionMethod.ELECTED_BY_VOTERS


def names_only_elected_by_members_roles(derived: DerivedRoles, taxonomy: Taxonomy) -> bool:
    """ "Vice Mayor": yes. "Mayor Pro Tem, District 3 Council Member": no, it names a post's role."""
    if not derived.roles:
        return False
    return all(_selection_method(role, taxonomy) == SelectionMethod.ELECTED_BY_MEMBERS for role in derived.roles)


def has_division(derived: DerivedRoles) -> bool:
    return any(part.parsed.division for part in derived.parts)


def _selection_method(role: str, taxonomy: Taxonomy) -> SelectionMethod:
    # A role the taxonomy has no method for keeps today's behaviour: it may be a post's role.
    return taxonomy.selection_methods.get(role, SelectionMethod.ELECTED_BY_VOTERS)


_SELECTION_METHOD_RANK = {
    SelectionMethod.ELECTED_BY_VOTERS: 0,
    SelectionMethod.ELECTED_BY_MEMBERS: 1,
    SelectionMethod.APPOINTED: 2,
}


def _winning_role(roles: list[str], taxonomy: Taxonomy) -> str | None:
    """Elected by voters, then by members, then appointed; config priority within each.
    "Mayor Pro Tem, District 3 Council Member" is a Council Member."""
    if not roles:
        return None

    def rank(role: str) -> tuple:
        return (_SELECTION_METHOD_RANK[_selection_method(role, taxonomy)], taxonomy.role_priority.get(role, 1_000_000), role)

    return min(roles, key=rank)


def _division_ocdid(parsed: list[ParsedLabel], jurisdiction_ocdid: str) -> str:
    """A person sits in at most one division; the first label naming one decides it."""
    located = next((p for p in parsed if p.division), None)
    return division_ocdid(located or ParsedLabel(), jurisdiction_ocdid)


def _unique(values: list[str]) -> list[str]:
    """Order-preserving, so the stored derivation reads the way the label did."""
    return list(dict.fromkeys(values))
