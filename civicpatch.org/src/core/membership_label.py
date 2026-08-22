"""What to call a person's post when nobody has said.

Pure. A reconstruction, not the source's own words — the page said "Councilmember Pos. 8" and
this yields "Council Member Position 8". Close enough to read, never close enough to trust,
which is why `memberships.label` exists for a person to overrule it.
"""

_DIVISION_LABELS = {
    "ward": "Ward",
    "council_district": "District",
    "district": "District",
    "precinct": "Precinct",
    "subdistrict": "Subdistrict",
}


def _division_phrase(division_ocdid: str) -> str | None:
    """ "District 3" from the division's last segment, or None if it names a whole government."""
    tail = division_ocdid.rsplit("/", 1)[-1]
    kind, _, value = tail.partition(":")
    name = _DIVISION_LABELS.get(kind)
    return f"{name} {value}" if name and value else None


def derive_label(
    role_label: str,
    division_ocdid: str,
    designations: list[str],
    unmatched_text: list[str],
) -> str:
    parts = [role_label, *designations]
    division = _division_phrase(division_ocdid)
    if division:
        parts.append(division)
    parts.extend(unmatched_text)
    return ", ".join(part for part in parts if part)
