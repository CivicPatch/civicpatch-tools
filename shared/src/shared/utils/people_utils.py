"""Ordering a roster the way a reviewer reads it: by role, then designation, then name.

`person_to_official` lived here and is gone. It joined a person's labels into one
`office.name` and lifted the division out — a render that could not be undone, so a person
sighted on three pages that spelled the office differently read back as three offices.
`people_roster._rendered` now builds the row straight off the `Person`, with the derivation's
single `label` beside the verbatim `labels`.

The reverse (`official_to_person`) went earlier, for the same reason.
"""

from typing import List

from shared.schemas import DerivedPerson
from shared.utils.label_parser import ParsedLabel, parse_label
from shared.utils.taxonomy import Taxonomy, designation_sort_key, role_sort_key


def _sortable_designations(parsed: ParsedLabel) -> List[str]:
    """The designations naming no division, plus the division — both order a roster."""
    if not parsed.division:
        return parsed.other_designations
    return parsed.other_designations + [
        f"{parsed.division.designation} {parsed.division.value}"
    ]


def person_sort_key(person: DerivedPerson, taxonomy: Taxonomy):
    """How a roster reads top to bottom: most senior role first, then the division or seat
    designation, then name.

    Exposed separately from `sort_people` so a caller holding a different shape — the publish
    boundary holds `PERSON_JSON` dicts, not `DerivedPerson` — can order by the same rule
    instead of writing a second one that drifts.
    """
    parsed = [parse_label(label, taxonomy) for label in person.labels]
    return (
        min(
            (role_sort_key(p.role or "", taxonomy) for p in parsed),
            default=role_sort_key("", taxonomy),
        ),
        min(
            (
                designation_sort_key(d, taxonomy)
                for p in parsed
                for d in _sortable_designations(p)
            ),
            default=designation_sort_key("", taxonomy),
        ),
        # Eight council members share a sort key. Without this the roster's order is
        # whatever order the records arrived in, which the read cannot reproduce.
        person.name,
    )


def sort_people(people: List[DerivedPerson], taxonomy: Taxonomy) -> list[DerivedPerson]:
    return sorted(people, key=lambda person: person_sort_key(person, taxonomy))


