"""What to call a person's seat, and what their labels said that the seat's name does not.

Pure, and a reconstruction — "Councilmember Pos. 8" yields "Council Member, Position 8". Close
enough to read, never to trust, which is why `memberships.label` can overrule it.

`derive_post_label` names the seat; `MembershipLabel` names one person in it.
"""

from pydantic import BaseModel

from core.people_roles import LabelPart

_DIVISION_LABELS = {
    "ward": "Ward",
    "council_district": "District",
    "district": "District",
    "precinct": "Precinct",
    "subdistrict": "Subdistrict",
}

_SEPARATOR = ", "


def _division_phrase(division_ocdid: str) -> str | None:
    """ "District 3" from the division's last segment, or None if it names a whole government."""
    tail = division_ocdid.rsplit("/", 1)[-1]
    kind, _, value = tail.partition(":")
    name = _DIVISION_LABELS.get(kind)
    return f"{name} {value}" if name and value else None


def derive_post_label(role_label: str, division_ocdid: str) -> str:
    """The seat's own name: role, then the division it covers."""
    parts = [role_label, _division_phrase(division_ocdid)]
    return _SEPARATOR.join(part for part in parts if part)


def rendered_post_label(
    post_label: str | None, role_label: str, division_ocdid: str
) -> str:
    """The stored name if a human gave one, else the derived one."""
    return post_label or derive_post_label(role_label, division_ocdid)


class MembershipLabel(BaseModel):
    """One person in one seat. Everything past `post_label` is about the occupant."""

    post_label: str
    demoted_roles: list[str] = []
    designations: list[str] = []
    unmatched_text: list[str] = []


def render(label: MembershipLabel) -> str:
    """One string, seat first — "Council Member, District 5, Place 2", so the shared part
    stays contiguous."""
    parts = [
        label.post_label,
        *label.demoted_roles,
        *label.designations,
        *label.unmatched_text,
    ]
    return _SEPARATOR.join(part for part in parts if part)


def proposed_membership_label(parts: list[LabelPart]) -> str | None:
    """`memberships.label` — the source's words for whatever the post label will not say.

    Per label rather than over their union: which designation came off which label is the
    order a reader expects, and a person named twice on one page keeps both readings apart.
    """
    label: list[str] = []
    for part in parts:
        for text in part.parsed.other_designations + part.parsed.unmatched:
            if text not in label:
                label.append(text)
    return _SEPARATOR.join(label) or None
