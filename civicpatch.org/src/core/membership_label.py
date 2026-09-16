"""What to call a person's seat, and what their labels said that the seat's name does not.

Pure, and a reconstruction — "Councilmember Pos. 8" yields "Council Member, Position 8". Close
enough to read, never to trust, which is why `memberships.label` can overrule it.

`derive_post_label` names the seat; `MembershipLabel` names one person in it — and only that:
the seat's own name is never folded in here, since every caller already has it separately
(the post it belongs to), and every consumer of `render`'s output shows it beside, not inside,
whatever this returns.
"""

from pydantic import BaseModel

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


class MembershipLabel(BaseModel):
    """What one occupant's own labels said beyond their seat's name."""

    demoted_roles: list[str] = []
    designations: list[str] = []
    unmatched_text: list[str] = []


def render(label: MembershipLabel) -> str:
    """One string, empty when the occupant's labels said nothing beyond the seat itself."""
    parts = [*label.demoted_roles, *label.designations, *label.unmatched_text]
    return _SEPARATOR.join(part for part in parts if part)


def render_with_post_label(post_label: str, label: MembershipLabel) -> str:
    """The self-contained form: seat first, then whatever `render` adds beyond it.

    For a caller with no separate place to show the seat's own name — a dense multi-town scan
    table (`batch_review.py`), not the per-person card, which shows the two beside each other
    and calls `render` directly instead.
    """
    parts = [post_label, *label.demoted_roles, *label.designations, *label.unmatched_text]
    return _SEPARATOR.join(part for part in parts if part)
