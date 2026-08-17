from typing import List

from domain.models import Office, Official, Person
from runners.people_collector.schemas import ResearchedPerson
from shared.utils.divisions import division_ocdid_to_designation
from shared.utils.label_parser import ParsedLabel, division_ocdid, parse_label
from shared.utils.official_fields import office_name_to_labels
from shared.utils.taxonomy import (
    Taxonomy,
    designation_sort_key,
    resolve_role,
    role_sort_key,
)


def filter_people_by_roles(
    people: List[ResearchedPerson], taxonomy: Taxonomy
) -> List[ResearchedPerson]:
    return [p for p in people if any(resolve_role(r, taxonomy) for r in p.roles)]


def _sortable_designations(parsed: ParsedLabel) -> List[str]:
    """The non-area designations plus the division — both order a roster, so both sort."""
    if not parsed.division:
        return parsed.other_designations
    return parsed.other_designations + [f"{parsed.division.designation} {parsed.division.value}"]


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


def official_to_person(official: Official, taxonomy: Taxonomy) -> Person:
    return Person(
        name=official.name,
        other_names=official.other_names,
        labels=office_name_to_labels(official.office.name)
        + division_ocdid_to_designation(
            official.office.division_ocdid, official.jurisdiction_ocdid
        ),
        phones=official.phones,
        emails=official.emails,
        urls=official.urls,
        start_date=official.start_date,
        end_date=official.end_date,
        image=official.image,
        jurisdiction_ocdid=official.jurisdiction_ocdid,
        cdn_image=official.cdn_image,
        source_urls=official.source_urls,
        updated_at=official.updated_at,
    )
