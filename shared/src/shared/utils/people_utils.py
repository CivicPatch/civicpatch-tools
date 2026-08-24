"""Rendering a roster into the shape it is stored in.

`Person` carries labels verbatim, one per office. `Official` joins them into a single
`office.name` with the division lifted out — a lossy render kept only until the review
surfaces read `labels`, which is what they now also receive.

The reverse (`official_to_person`) is gone: it split `office.name` back apart and put the
division into the labels as a designation, and nothing called it once records crossed the
boundary already decomposed.
"""

from typing import List

from shared.schemas import Office, Official, Person
from shared.utils.label_parser import ParsedLabel, division_ocdid, parse_label
from shared.utils.taxonomy import Taxonomy, designation_sort_key, role_sort_key


def _sortable_designations(parsed: ParsedLabel) -> List[str]:
    """The designations naming no division, plus the division — both order a roster."""
    if not parsed.division:
        return parsed.other_designations
    return parsed.other_designations + [
        f"{parsed.division.designation} {parsed.division.value}"
    ]


def sort_people(people: List[Person], taxonomy: Taxonomy) -> list[Person]:
    def person_sort_key(person: Person):
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
        )

    return sorted(people, key=person_sort_key)


def person_to_official(person: Person, taxonomy: Taxonomy) -> Official:
    parsed = [parse_label(label, taxonomy) for label in person.labels]
    office_names = list(dict.fromkeys(label for label in person.labels if label))
    office_name = " - ".join(office_names) if office_names else "Unknown Office"
    # A person sits in at most one division; the first label naming one decides it.
    located = next((p for p in parsed if p.division), None)
    resolved_division = division_ocdid(
        located or ParsedLabel(), person.jurisdiction_ocdid
    )
    return Official(
        id="",  # to be filled in later after resolving with API
        name=person.name,
        other_names=person.other_names,
        phones=person.phones,
        emails=person.emails,
        urls=person.urls,
        start_date=person.start_date or None,
        end_date=person.end_date or None,
        office=Office(
            name=office_name,
            division_ocdid=resolved_division,
        ),
        image=person.image,
        jurisdiction_ocdid=person.jurisdiction_ocdid,
        cdn_image=person.cdn_image,
        source_urls=person.source_urls,
        updated_at=person.updated_at or "",
    )


