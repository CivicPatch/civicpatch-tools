"""Which office a person's labels imply: the role that won, the division, what matched nothing.

`shared.utils.label_parser` reads one label; this decides across every label one person was
seen under, which is the decision a single label cannot make.

Pure — labels and a taxonomy in, structure out — and never stored. A parser fix therefore
changes what history means without any row needing to be rewritten, which is why
`source_records` keeps labels verbatim and nothing derived.

The decision, not its rendering: `post_derivation` turns this into posts, and
`membership_label` turns it into words.
"""

from pydantic import BaseModel

from shared.utils.label_parser import ParsedLabel, division_ocdid, parse_label
from shared.utils.taxonomy import Taxonomy


class LabelPart(BaseModel):
    """One raw label beside what the parser made of it.

    Kept paired rather than flattened: which designation came off which label is the thing a
    person named twice on one page needs, and a flat union cannot say it.
    """

    label: str
    parsed: ParsedLabel


class DerivedRoles(BaseModel):
    """What one person's labels imply, split by who owns each part.

    Was a bare dict, which is why the two callers could quietly read different keys — and why
    `people_roster` and `post_derivation` both parsing the same labels went unnoticed.

    `role` and `division_ocdid` identify the **post**; `other_designations` and `unmatched`
    describe the **person in it**; `roles` past the winner become the membership's demoted
    roles. `post_derivation` reads all of it, `people_roster` reads the first two.
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
    return DerivedRoles(
        labels=labels,
        parts=[
            LabelPart(label=label, parsed=part)
            for label, part in zip(labels, parsed)
        ],
        role=_winning_role(parsed, taxonomy),
        roles=_unique([role for p in parsed for role in p.roles]),
        division_ocdid=_division_ocdid(parsed, jurisdiction_ocdid),
        other_designations=_unique([d for p in parsed for d in p.other_designations]),
        unmatched=_unique([term for p in parsed for term in p.unmatched]),
    )


def _winning_role(parsed: list[ParsedLabel], taxonomy: Taxonomy) -> str | None:
    """The role published after the usurp — highest priority across every label."""
    roles = [p.role for p in parsed if p.role]
    if not roles:
        return None
    return min(
        roles, key=lambda role: (taxonomy.role_priority.get(role, 1_000_000), role)
    )


def _division_ocdid(parsed: list[ParsedLabel], jurisdiction_ocdid: str) -> str:
    """A person sits in at most one division; the first label naming one decides it."""
    located = next((p for p in parsed if p.division), None)
    return division_ocdid(located or ParsedLabel(), jurisdiction_ocdid)


def _unique(values: list[str]) -> list[str]:
    """Order-preserving, so the stored derivation reads the way the label did."""
    return list(dict.fromkeys(values))
