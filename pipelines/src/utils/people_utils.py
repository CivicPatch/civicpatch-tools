from typing import List

from domain.models import Office, Official, Person
from runners.people_collector.schemas import ResearchedPerson
from utils.divisions import (
    designations_without_division,
    division_ocdid_to_designation,
    resolve_division,
)
from utils.taxonomy import (
    Taxonomy,
    designation_sort_key,
    resolve_role,
    role_sort_key,
)


def filter_people_by_roles(
    people: List[ResearchedPerson], taxonomy: Taxonomy
) -> List[ResearchedPerson]:
    return [p for p in people if any(resolve_role(r, taxonomy) for r in p.roles)]


def office_name_to_roles(office_name: str, taxonomy: Taxonomy) -> List[str]:
    if not office_name or office_name == "Unknown Office":
        return []
    parts = [p.strip() for p in office_name.split(" - ") if p.strip()]
    return [p for p in parts if resolve_role(p, taxonomy)]


def sort_people(people: List[Person], taxonomy: Taxonomy) -> list[Person]:
    def person_sort_key(person: Person):
        return (
            min(
                (role_sort_key(role, taxonomy) for role in person.roles),
                default=role_sort_key("", taxonomy),
            ),
            min(
                (designation_sort_key(d, taxonomy) for d in person.designations),
                default=designation_sort_key("", taxonomy),
            ),
        )

    return sorted(people, key=person_sort_key)


def person_to_official(person: Person) -> Official:
    office_names = list(
        dict.fromkeys(person.roles + designations_without_division(person.designations))
    )
    office_name = " - ".join(office_names) if office_names else "Unknown Office"
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
            division_ocdid=resolve_division(
                person.jurisdiction_ocdid, person.designations
            ),
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
        roles=office_name_to_roles(official.office.name, taxonomy),
        designations=division_ocdid_to_designation(
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
